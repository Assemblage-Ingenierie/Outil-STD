"""
Dé-sérialisation pickle restreinte (défense en profondeur).

Les fichiers projet (``.stdproj``) et le cache disque sont des pickles. Charger un
pickle arbitraire peut exécuter du code (``pickle`` reconstruit des objets via des
appels arbitraires). Comme un ``.stdproj`` peut être échangé entre postes, un
fichier malveillant représente un risque d'exécution de code.

Cet ``Unpickler`` restreint n'autorise que les modules nécessaires à reconstruire
des DataFrames pandas, des tableaux numpy et les objets simples de l'application,
et bloque tout le reste (``os``, ``subprocess``, ``builtins.eval``…). Ce n'est pas
une garantie absolue, mais cela neutralise les charges utiles pickle classiques
(``os.system`` & co.) sans changer le format des fichiers existants.
"""
from __future__ import annotations
import io
import pickle

# Modules (par package de tête) dont on autorise la reconstruction.
_PACKAGES_AUTORISES = {
    "pandas",      # DataFrame / Series / Index / blocs internes
    "numpy",       # ndarray, dtypes, scalaires
    "pyarrow",     # colonnes texte Arrow (backend par défaut de pandas 3.x)
    "collections",
    "datetime",
    "decimal",
    "copyreg",     # __newobj__ / _reconstructor (protocole pickle)
    "zoneinfo",
    "pytz",
    "core",        # core.variante.Variante (objets de l'application)
}

# Fonctions/classes de ``builtins`` autorisées : conteneurs et scalaires sûrs
# uniquement. On exclut volontairement eval, exec, getattr, __import__, open…
_BUILTINS_AUTORISES = {
    "list", "dict", "tuple", "set", "frozenset", "bytearray", "bytes",
    "int", "float", "complex", "str", "bool", "object", "range", "slice",
}


class _UnpicklerRestreint(pickle.Unpickler):
    def find_class(self, module, name):
        if module == "builtins":
            if name in _BUILTINS_AUTORISES:
                return super().find_class(module, name)
            raise pickle.UnpicklingError(
                f"Global refusé pour raison de sécurité : builtins.{name}")
        if module.split(".", 1)[0] in _PACKAGES_AUTORISES:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(
            f"Global refusé pour raison de sécurité : {module}.{name}")


def charger_securise(fileobj):
    """Charge un pickle depuis un objet fichier via l'Unpickler restreint.
    Lève ``pickle.UnpicklingError`` si le contenu référence un global interdit."""
    return _UnpicklerRestreint(fileobj).load()


def charger_bytes_securise(data: bytes):
    """Idem depuis un buffer d'octets."""
    return _UnpicklerRestreint(io.BytesIO(data)).load()
