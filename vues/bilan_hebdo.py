from src import ui, vue_semaine

db = ui.db()
ui.page("Bilan hebdo", "MASI, MASI 20 et marché à terme : la semaine en un rapport Word", db["masi20"]["date"].max())
vue_semaine.afficher(db)
ui.pied()
