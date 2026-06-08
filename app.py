from flask import Flask, render_template, url_for, g, request, redirect, flash

from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date
import sqlite3
DATABASE = "database.db"
app = Flask(__name__)
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

app.route("/register")
def register():
    if request.method == "POST":
        username = request.form['username']
        password = generate_password_hash[request.form['password']]
        return ("home.html")
        

@app.route("/")
def home():
    sql = '''SELECT category.id, category.name, category.spending_limit,
            IFNULL(SUM(expenses.amount_spent), 0) AS total_amount_spent
            FROM category
            LEFT JOIN expenses ON category.id = expenses.category_id
            GROUP BY category.id'''
    categories = query_db(sql)
    get_db().commit()
    return render_template("home.html", categories = categories)

@app.route("/categories")
def view_categories():
    sql = "SELECT * FROM category"
    categories = query_db(sql)
    return render_template("categories.html", categories = categories)

@app.route ("/add_category", methods = ["POST"])
def add_category():
    category_name = request.form ['name']
    spending_limit = request.form ['spending_limit']
    sql = "INSERT INTO category (name, spending_limit) VALUES (?, ?)"
    query_db(sql,(category_name, spending_limit,))
    get_db().commit()
    return redirect (url_for("view_categories"))

@app.route ("/edit_category/<int:id>", methods = ["POST"])
def edit_category(id):
    category_name = request.form ['name']
    spending_limit = request.form ['spending_limit']
    sql = "UPDATE category SET name =?, spending_limit = ? WHERE id = ?"
    query_db(sql,(category_name, spending_limit,id,))
    get_db().commit()
    return redirect (url_for("view_categories"))

@app.route("/delete_category/<int:id>")
def delete_category(id):
    sql = "DELETE FROM category WHERE id =?"
    query_db(sql,(id,))
    sql = "DELETE FROM expenses WHERE id =?"
    query_db(sql,(id,))
    get_db().commit()
    return redirect (url_for("view_categories"))


@app.route("/view_expenses")
def view_expenses():
    sql = "SELECT expenses.id, expenses.name, expenses.amount_spent, expenses. date, category.name AS category FROM expenses JOIN category ON expenses.category_id = category.id"
    expenses = query_db(sql)
    sql = "SELECT * FROM category"
    categories = query_db(sql)
    return render_template("expenses.html", expenses=expenses, categories=categories)

@app.route ("/add_expenses", methods = ["POST"])
def add_expenses():
    category_id = request.form['category_id']
    expenses_name = request.form ['name']
    amount_spent = request.form ['amount_spent']
    sql = "INSERT INTO expenses (category_id, name, amount_spent) VALUES (?, ?, ?)"
    query_db(sql,(category_id, expenses_name, amount_spent,))
    get_db().commit()    
    return redirect (url_for("view_expenses"))

@app.route ("/edit_expenses/<int:id>", methods = ["POST"])
def edit_expenses(id):
    category_id = request.form['category_id']
    expenses_name = request.form ['name']
    amount_spent = request.form ['amount_spent']
    sql = "UPDATE expenses SET category_id =?, name =?, amount_spent = ? WHERE id = ?"
    query_db(sql,(category_id, expenses_name, amount_spent,id,))
    get_db().commit()
    return redirect (url_for("view_expenses"))
    

@app.route("/delete_expenses/<int:id>")
def delete_expenses(id):
    sql = "DELETE FROM expenses WHERE id =?"
    query_db(sql,(id,))
    get_db().commit()
    return redirect (url_for("view_expenses"))



if __name__ == "__main__":
    app.run(debug= True)
