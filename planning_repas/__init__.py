# -*- coding: utf-8 -*-
"""Module Planning repas pour Gestion Cantine.

Intégration en deux lignes dans l'application hôte :

    from planning_repas import CadrePlanningRepas
    notebook.add(CadrePlanningRepas(notebook, chemin_db="cantine.db"),
                 text="Planning repas")

Le module crée ses propres tables (préfixe `pr_`) dans la base que tu lui
passes. Il ne touche à aucune table existante.

db, generateur et export s'importent sans Tkinter : le moteur reste
utilisable en script, pour un export automatisé par exemple.
"""

__version__ = "1.1.0"

from . import db, generateur, export

__all__ = ["CadrePlanningRepas", "db", "generateur", "export", "__version__"]


def __getattr__(nom):
    """Import differé de l'interface : Tkinter n'est chargé qu'à l'usage."""
    if nom == "CadrePlanningRepas":
        from .ui import CadrePlanningRepas
        return CadrePlanningRepas
    raise AttributeError(f"module {__name__!r} n'a pas d'attribut {nom!r}")
