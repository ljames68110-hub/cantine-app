# -*- coding: utf-8 -*-
"""
securite.py — Chiffrement de la base Cantine avec déni plausible (2 mots de passe).

Un unique fichier conteneur (taille fixe, remplissage aléatoire) contient :
  - un compartiment PARTAGÉ (toutes les données SAUF les créances) ;
  - un compartiment SECRET (les créances) caché dans le remplissage.

Deux mots de passe :
  - A (COMPLET) : déchiffre le partagé ET le secret.
  - B (PROPRE)  : déchiffre UNIQUEMENT le partagé. Aucune clé vers le secret,
    ne peut pas le lire ni prouver qu'il existe (il ressemble à du remplissage).

La longueur/emplacement du secret n'est stockée nulle part en clair : seule la
« fente » du mot de passe A (chiffrée) la contient.

Format du fichier :
  MAGIC(8) | salt(16) | fenteA(124) | fenteB(124) | shared_len(8)
          | shared_blob | secret_blob | remplissage_aleatoire -> TAILLE_FIXE

  Offset du secret = _HEADER_LEN + shared_len (calculé, pas stocké).
  Fente (plaintext, rembourré à 96) : mode(1)|MK_shared(32)|MK_secret(32)|secret_len(8)
"""

import os
import struct
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC          = b"CANT1\x00\x00\x00"
SALT_LEN       = 16
KEY_LEN        = 32
NONCE_LEN      = 12
MK_LEN         = 32
_SCRYPT_N      = 2 ** 14
_SCRYPT_R      = 8
_SCRYPT_P      = 1

MODE_FULL      = 1
MODE_CLEAN     = 2

_SLOT_PLAIN_PAD = 96
_SLOT_CT_LEN    = NONCE_LEN + _SLOT_PLAIN_PAD + 16        # 124
_HEADER_LEN     = len(MAGIC) + SALT_LEN + 2 * _SLOT_CT_LEN + 8

TAILLE_FIXE     = 8 * 1024 * 1024                          # 8 Mo


class MauvaisMotDePasse(Exception):
    pass


def _kdf(mot_de_passe, salt):
    return Scrypt(salt=salt, length=KEY_LEN,
                  n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P).derive(
                      mot_de_passe.encode("utf-8"))


def _chiffrer(cle, donnees):
    nonce = os.urandom(NONCE_LEN)
    return nonce + AESGCM(cle).encrypt(nonce, donnees, None)


def _dechiffrer(cle, blob):
    return AESGCM(cle).decrypt(blob[:NONCE_LEN], blob[NONCE_LEN:], None)


def _emballer_fente(slot_key, mode, mk_shared, mk_secret, secret_len):
    plain = struct.pack("<B", mode) + mk_shared + mk_secret + struct.pack("<Q", secret_len)
    plain = plain + os.urandom(_SLOT_PLAIN_PAD - len(plain))
    return _chiffrer(slot_key, plain)


def _ouvrir_fente(slot_key, fente_ct):
    try:
        plain = _dechiffrer(slot_key, fente_ct)
    except Exception:
        return None
    mode = plain[0]
    mk_shared = plain[1:1 + MK_LEN]
    mk_secret = plain[1 + MK_LEN:1 + 2 * MK_LEN]
    secret_len, = struct.unpack("<Q", plain[1 + 2 * MK_LEN:1 + 2 * MK_LEN + 8])
    return mode, mk_shared, mk_secret, secret_len


def _taille_cible(shared_blob_len, besoin_secret):
    """Taille fixe (multiple de TAILLE_FIXE) garantissant la place du secret."""
    reserve = _HEADER_LEN + shared_blob_len + besoin_secret
    t = TAILLE_FIXE
    while t < reserve:
        t += TAILLE_FIXE
    return t


def _ecrire(chemin, salt, fenteA, fenteB, shared_blob, tail):
    """Écrit l'en-tête + partagé + `tail` (= secret + remplissage), ajusté à une
    taille fixe. `tail` contient déjà le secret au début ; on ne rogne que le
    remplissage de fin."""
    entete = MAGIC + salt + fenteA + fenteB + struct.pack("<Q", len(shared_blob))
    assert len(entete) == _HEADER_LEN, (len(entete), _HEADER_LEN)
    corps = entete + shared_blob + tail
    # On garde au moins 1 Mo de marge pour que le secret (au début de tail) ne
    # soit jamais rogné.
    target = _taille_cible(len(shared_blob), 1024 * 1024)
    if len(corps) > target:
        corps = corps[:target]                 # ne rogne que le remplissage final
    else:
        corps += os.urandom(target - len(corps))
    tmp = chemin + ".tmp"
    with open(tmp, "wb") as f:
        f.write(corps)
    os.replace(tmp, chemin)


def est_conteneur_chiffre(chemin):
    try:
        with open(chemin, "rb") as f:
            return f.read(len(MAGIC)) == MAGIC
    except Exception:
        return False


def creer_conteneur(chemin, mdp_a, mdp_b, data_shared, data_secret):
    if mdp_a == mdp_b:
        raise ValueError("Les deux mots de passe doivent être différents.")
    salt = os.urandom(SALT_LEN)
    mk_shared = os.urandom(MK_LEN)
    mk_secret = os.urandom(MK_LEN)
    shared_blob = _chiffrer(mk_shared, data_shared)
    secret_blob = _chiffrer(mk_secret, data_secret or b"")
    fenteA = _emballer_fente(_kdf(mdp_a, salt), MODE_FULL, mk_shared, mk_secret, len(secret_blob))
    fenteB = _emballer_fente(_kdf(mdp_b, salt), MODE_CLEAN, mk_shared, os.urandom(MK_LEN), 0)
    _ecrire(chemin, salt, fenteA, fenteB, shared_blob, secret_blob)


def ouvrir_conteneur(chemin, mot_de_passe):
    with open(chemin, "rb") as f:
        buf = f.read()
    if buf[:len(MAGIC)] != MAGIC:
        raise ValueError("Fichier non reconnu (pas un conteneur chiffré).")
    o = len(MAGIC)
    salt = buf[o:o + SALT_LEN]; o += SALT_LEN
    fenteA = buf[o:o + _SLOT_CT_LEN]; o += _SLOT_CT_LEN
    fenteB = buf[o:o + _SLOT_CT_LEN]; o += _SLOT_CT_LEN
    shared_len, = struct.unpack("<Q", buf[o:o + 8]); o += 8
    shared_blob = buf[o:o + shared_len]
    secret_zone_off = _HEADER_LEN + shared_len

    slot_key = _kdf(mot_de_passe, salt)
    infos = _ouvrir_fente(slot_key, fenteA)
    which = "A"
    if infos is None:
        infos = _ouvrir_fente(slot_key, fenteB)
        which = "B"
    if infos is None:
        raise MauvaisMotDePasse()

    mode, mk_shared, mk_secret, secret_len = infos
    data_shared = _dechiffrer(mk_shared, shared_blob)
    secret_blob = buf[secret_zone_off:secret_zone_off + secret_len] if secret_len else b""
    # Tout ce qui suit le partagé (secret + remplissage) : sert à PRÉSERVER le
    # secret en mode propre, sans que B ait besoin de connaître sa longueur.
    tail = buf[secret_zone_off:]

    data_secret = None
    if mode == MODE_FULL and secret_len > 0:
        try:
            data_secret = _dechiffrer(mk_secret, secret_blob)
        except Exception:
            data_secret = b""

    ctx = {
        "salt": salt, "slot_key": slot_key, "mode": mode,
        "mk_shared": mk_shared,
        "mk_secret": mk_secret if mode == MODE_FULL else None,
        "fenteA": fenteA, "fenteB": fenteB,
        "secret_blob": secret_blob,            # original (mode complet)
        "tail": tail,                          # secret+remplissage (mode propre)
    }
    return {
        "mode": "full" if mode == MODE_FULL else "clean",
        "data_shared": data_shared,
        "data_secret": data_secret,
        "_ctx": ctx,
    }


def sauvegarder_conteneur(chemin, ctx, data_shared, data_secret):
    """Réécrit le conteneur.
    - mode complet : ré-chiffre partagé ET secret ; met à jour la fente A.
    - mode propre  : ré-chiffre le partagé, PRÉSERVE le secret et les 2 fentes."""
    shared_blob = _chiffrer(ctx["mk_shared"], data_shared)
    if ctx["mode"] == MODE_FULL and ctx["mk_secret"] is not None:
        secret_blob = _chiffrer(ctx["mk_secret"], data_secret or b"")
        fenteA = _emballer_fente(ctx["slot_key"], MODE_FULL, ctx["mk_shared"],
                                 ctx["mk_secret"], len(secret_blob))
        fenteB = ctx["fenteB"]
        tail = secret_blob                      # le remplissage est ajouté par _ecrire
    else:
        # Mode propre : on préserve tout le bloc (secret + remplissage) tel quel.
        fenteA = ctx["fenteA"]
        fenteB = ctx["fenteB"]
        tail = ctx.get("tail", ctx.get("secret_blob", b""))
    _ecrire(chemin, ctx["salt"], fenteA, fenteB, shared_blob, tail)
