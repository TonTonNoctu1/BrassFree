from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

# -------------------
# ⚙️ Configuration
# -------------------
app = Flask(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "brasserie_v13.db")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + DB_PATH
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = "secret_key"

db = SQLAlchemy(app)
print("→ Base SQLite utilisée :", DB_PATH)

# -------------------
# 🔹 Modèles
# -------------------
class Stock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(50), nullable=False)
    quantite = db.Column(db.Float, nullable=False, default=0)
    unite = db.Column(db.String(20), nullable=False, default="kg")
    fournisseur = db.Column(db.String(50))
    seuil_alerte = db.Column(db.Float, nullable=False, default=0)

class Recette(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(50), nullable=False)
    ingredients = db.relationship('RecetteIngredient', backref='recette', cascade="all, delete-orphan")

class RecetteIngredient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recette_id = db.Column(db.Integer, db.ForeignKey('recette.id'), nullable=False)
    stock_id = db.Column(db.Integer, db.ForeignKey('stock.id'), nullable=False)
    quantite_par_litre = db.Column(db.Float, nullable=False)
    stock = db.relationship('Stock')

class Lot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(50), nullable=False)
    type_produit = db.Column(db.String(20), nullable=False)
    recette_id = db.Column(db.Integer, db.ForeignKey('recette.id'), nullable=True)
    volume = db.Column(db.Float, nullable=False)
    taille_unite = db.Column(db.Float, default=0.33)
    nb_unites = db.Column(db.Integer, nullable=False)
    nb_unites_vendues = db.Column(db.Integer, default=0)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    recette = db.relationship('Recette')

class Vente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lot_id = db.Column(db.Integer, db.ForeignKey('lot.id'), nullable=False)
    client = db.Column(db.String(50), nullable=False)
    nb_unites = db.Column(db.Integer, nullable=False)
    prix_unitaire = db.Column(db.Float, nullable=False, default=0.0)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    lot = db.relationship('Lot')

# -------------------
# 🔹 Création des tables
# -------------------
with app.app_context():
    db.create_all()
    print("→ Tables créées (si elles n'existaient pas)")

# -------------------
# 🔹 Fonctions utilitaires
# -------------------
def convert_to_base_unit(qte, unite):
    if unite.lower() in ['g', 'gramme', 'grammes']:
        return qte / 1000, 'kg'
    elif unite.lower() in ['ml']:
        return qte / 1000, 'L'
    elif unite.lower() in ['cl']:
        return qte / 100, 'L'
    return qte, unite

def display_unit(qte, unite):
    if unite.lower() == 'kg' and qte < 1:
        return qte*1000, 'g'
    elif unite.lower() == 'l' and qte < 1:
        return qte*1000, 'ml'
    return qte, unite

# -------------------
# 🔹 Routes Stock
# -------------------
@app.route('/stock')
def stock():
    tous_stocks = Stock.query.all()
    alertes = [s for s in tous_stocks if s.quantite <= s.seuil_alerte]
    return render_template('stock.html', stocks=tous_stocks, alertes=alertes, display_unit=display_unit)

@app.route('/ajouter_stock', methods=['GET', 'POST'])
def ajouter_stock():
    if request.method == 'POST':
        nom = request.form['nom']
        quantite, unite = convert_to_base_unit(float(request.form['quantite']), request.form['unite'])
        fournisseur = request.form['fournisseur']
        seuil_alerte, _ = convert_to_base_unit(float(request.form['seuil_alerte']), request.form['unite'])
        nouveau_stock = Stock(nom=nom, quantite=quantite, unite=unite, fournisseur=fournisseur, seuil_alerte=seuil_alerte)
        db.session.add(nouveau_stock)
        db.session.commit()
        flash(f"{nom} ajouté au stock !", "success")
        return redirect(url_for('stock'))
    return render_template('ajouter_stock.html')

@app.route('/supprimer_stock/<int:stock_id>', methods=['POST'])
def supprimer_stock(stock_id):
    stock = Stock.query.get_or_404(stock_id)
    if RecetteIngredient.query.filter_by(stock_id=stock.id).first():
        flash("Impossible de supprimer ce stock : utilisé dans une recette !", "danger")
        return redirect(url_for('stock'))
    db.session.delete(stock)
    db.session.commit()
    flash(f"Stock {stock.nom} supprimé !", "success")
    return redirect(url_for('stock'))

# -------------------
# 🔹 Routes Recettes
# -------------------
@app.route('/recettes')
def recettes():
    toutes_recettes = Recette.query.all()
    return render_template('recettes.html', recettes=toutes_recettes, stocks=Stock.query.all(), display_unit=display_unit)

@app.route('/ajouter_recette', methods=['GET', 'POST'])
def ajouter_recette():
    stocks = Stock.query.all()
    if request.method == 'POST':
        nom = request.form['nom']
        recette = Recette(nom=nom)
        db.session.add(recette)
        db.session.commit()

        stock_ids = request.form.getlist('stock_id[]')
        quantites = request.form.getlist('quantite_par_litre[]')
        for stock_id, q in zip(stock_ids, quantites):
            if stock_id and q:
                ingredient = RecetteIngredient(
                    recette_id=recette.id,
                    stock_id=int(stock_id),
                    quantite_par_litre=float(q)
                )
                db.session.add(ingredient)
        db.session.commit()
        flash(f"Recette {nom} ajoutée avec ses ingrédients !", "success")
        return redirect(url_for('recettes'))
    return render_template('ajouter_recette.html', stocks=stocks)

@app.route('/modifier_recette/<int:recette_id>', methods=['GET', 'POST'])
def modifier_recette(recette_id):
    recette = Recette.query.get_or_404(recette_id)
    stocks = Stock.query.all()
    if request.method == 'POST':
        recette.nom = request.form['nom']
        db.session.query(RecetteIngredient).filter_by(recette_id=recette.id).delete()
        stock_ids = request.form.getlist('stock_id[]')
        quantites = request.form.getlist('quantite_par_litre[]')
        for stock_id, q in zip(stock_ids, quantites):
            if stock_id and q:
                ingredient = RecetteIngredient(
                    recette_id=recette.id,
                    stock_id=int(stock_id),
                    quantite_par_litre=float(q)
                )
                db.session.add(ingredient)
        db.session.commit()
        flash(f"Recette {recette.nom} modifiée !", "success")
        return redirect(url_for('recettes'))
    return render_template('modifier_recette.html', recette=recette, stocks=stocks)

@app.route('/supprimer_recette/<int:recette_id>', methods=['POST'])
def supprimer_recette(recette_id):
    recette = Recette.query.get_or_404(recette_id)
    db.session.delete(recette)
    db.session.commit()
    flash(f"Recette {recette.nom} supprimée !", "success")
    return redirect(url_for('recettes'))

@app.route('/utiliser_recette/<int:recette_id>', methods=['POST'])
def utiliser_recette(recette_id):
    recette = Recette.query.get_or_404(recette_id)
    volume = float(request.form.get('volume', 1))
    for ing in recette.ingredients:
        if ing.stock.quantite < ing.quantite_par_litre * volume:
            flash(f"Stock insuffisant pour {ing.stock.nom}", "danger")
            return redirect(url_for('recettes'))
    for ing in recette.ingredients:
        ing.stock.quantite -= ing.quantite_par_litre * volume
    db.session.commit()
    flash(f"Recette '{recette.nom}' utilisée ({volume} L) : stock mis à jour", "success")
    return redirect(url_for('recettes'))

# -------------------
# 🔹 Routes Lots
# -------------------
@app.route('/lots')
def lots():
    tous_lots = Lot.query.order_by(Lot.date.desc()).all()
    for lot in tous_lots:
        lot.nb_restantes = lot.nb_unites - lot.nb_unites_vendues
    return render_template('lots.html', lots=tous_lots, display_unit=display_unit)

@app.route('/ajouter_lot', methods=['GET', 'POST'])
def ajouter_lot():
    recettes = Recette.query.all()
    if request.method == 'POST':
        nom = request.form['nom']
        type_produit = request.form['type_produit']
        recette_id = request.form.get('recette_id') or None
        volume = float(request.form['volume'])
        taille_unite = float(request.form['taille_unite'])
        nb_unites = int(volume / taille_unite)

        lot = Lot(
            nom=nom,
            type_produit=type_produit,
            recette_id=recette_id,
            volume=volume,
            taille_unite=taille_unite,
            nb_unites=nb_unites
        )
        db.session.add(lot)

        if type_produit == "bière" and recette_id:
            recette = Recette.query.get(recette_id)
            for ing in recette.ingredients:
                ing.stock.quantite -= ing.quantite_par_litre * volume

        db.session.commit()
        flash(f"Lot {nom} ({type_produit}) ajouté !", "success")
        return redirect(url_for('lots'))
    return render_template('ajouter_lot.html', recettes=recettes)

@app.route('/supprimer_lot/<int:lot_id>', methods=['POST'])
def supprimer_lot(lot_id):
    lot = Lot.query.get_or_404(lot_id)
    if lot.nb_unites_vendues > 0:
        flash(f"Impossible de supprimer {lot.nom} : des ventes ont déjà été effectuées.", "danger")
        return redirect(url_for('lots'))
    db.session.delete(lot)
    db.session.commit()
    flash(f"Lot {lot.nom} supprimé avec succès !", "success")
    return redirect(url_for('lots'))

# -------------------
# 🔹 Routes Ventes
# -------------------
@app.route('/ventes')
def ventes():
    toutes_ventes = Vente.query.order_by(Vente.date.desc()).all()
    return render_template('ventes.html', ventes=toutes_ventes)

@app.route('/ajouter_vente', methods=['GET', 'POST'])
def ajouter_vente():
    lots = Lot.query.filter(Lot.nb_unites > Lot.nb_unites_vendues).all()
    if request.method == 'POST':
        client = request.form['client']
        lot_id = int(request.form['lot_id'])
        nb_unites = int(request.form['nb_unites'])
        prix_unitaire = float(request.form['prix_unitaire'])

        lot = Lot.query.get_or_404(lot_id)
        stock_restant = lot.nb_unites - lot.nb_unites_vendues
        if nb_unites > stock_restant:
            flash("Erreur : pas assez d'unités disponibles", "danger")
            return redirect(url_for('ajouter_vente'))

        vente = Vente(
            lot_id=lot.id,
            client=client,
            nb_unites=nb_unites,
            prix_unitaire=prix_unitaire
        )
        lot.nb_unites_vendues += nb_unites
        db.session.add(vente)
        db.session.commit()
        flash(f"Vente de {nb_unites} unités à {client} ajoutée !", "success")
        return redirect(url_for('ventes'))
    return render_template('ajouter_vente.html', lots=lots)

# -------------------
# 🔹 Accueil
# -------------------
@app.route('/')
def home():
    return redirect(url_for('stock'))

# -------------------
# ⚡ Lancement
# -------------------
if __name__ == '__main__':
    app.run(debug=True)
