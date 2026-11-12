"""Lance la maquette graphique depuis la racine du projet."""
import sys
from PyQt6.QtWidgets import QApplication
from src.interface.main import FenetrePrincipale

if __name__ == "__main__":
    application = QApplication(sys.argv)
    fenetre = FenetrePrincipale()
    fenetre.show()
    sys.exit(application.exec())
