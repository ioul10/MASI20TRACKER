from src import ui, vue_semaine

db = ui.db()
ui.page("Bilan hebdo", "Marché spot et marché à terme : la semaine en un rapport", db["masi20"]["date"].max())
vue_semaine.afficher(db)
ui.pied()
