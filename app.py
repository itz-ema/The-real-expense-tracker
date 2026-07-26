from flask import Flask, render_template, url_for, g, request, redirect, flash, session
from flask_login import LoginManager, login_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
import datetime
import sqlite3


DATABASE = "database.db"
app = Flask(__name__)

app.config['SECRET_KEY'] = 'itsasecret'


def ensure_schema():
    """Ensure the DB has user_id columns on category and expenses tables."""
    db = sqlite3.connect(DATABASE)
    cur = db.cursor()
    try:
        cur.execute("ALTER TABLE category ADD COLUMN user_id INTEGER")
    except sqlite3.OperationalError:
        # column probably exists
        pass
    try:
        cur.execute("ALTER TABLE expenses ADD COLUMN user_id INTEGER")
    except sqlite3.OperationalError:
        pass
    db.commit()
    db.close()


ensure_schema()

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



        

@app.route("/")
def home():
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    user_id = user[0]

    sql = '''SELECT category.id, category.name, category.spending_limit,
            IFNULL(SUM(expenses.amount_spent), 0) AS total_amount_spent
            FROM category
            LEFT JOIN expenses ON category.id = expenses.category_id
            WHERE category.user_id = ?
            GROUP BY category.id'''
    categories = query_db(sql, args=(user_id,))
    get_db().commit()
    username = user[1]
    return render_template("home.html", categories=categories, username=username)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        name = request.form["name"]
        password = request.form["password"]
        sql = "SELECT id, name, password FROM user WHERE name = ?"
        user = query_db(sql,args=(name,), one=True)

        if user and check_password_hash(user[2], password):
            session["user"] = user
            flash("Logged in successfully")
            return redirect(url_for("home"))
        if user:
            if check_password_hash(user[2], password):
                session['user']= user
                flash("Logged in successfully")
            else:
                flash('Password incorrect')
        else:
            flash ('Username does not exist')
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name") or request.form.get("username")
        password = request.form.get("password")

        if not name or not password:
            flash("Please enter both username and password")
            return render_template("register.html")

        password_hash = generate_password_hash(password)
        sql = "INSERT INTO user (name, password) VALUES (?, ?)"
        query_db(sql, (name, password_hash))
        get_db().commit()
        flash("Registration successful!")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/categories")
def view_categories():
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    user_id = user[0]
    sql = "SELECT * FROM category WHERE user_id = ?"
    categories = query_db(sql, args=(user_id,))
    return render_template("categories.html", categories=categories)

@app.route ("/add_category", methods = ["POST"])
def add_category():
    category_name = request.form ['name']
    spending_limit = request.form ['spending_limit']
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    user_id = user[0]
    sql = "INSERT INTO category (name, spending_limit, user_id) VALUES (?, ?, ?)"
    query_db(sql,(category_name, spending_limit, user_id,))
    get_db().commit()
    return redirect (url_for("view_categories"))

@app.route ("/edit_category/<int:id>", methods = ["POST"])
def edit_category(id):
    category_name = request.form ['name']
    spending_limit = request.form ['spending_limit']
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    user_id = user[0]
    sql = "UPDATE category SET name =?, spending_limit = ? WHERE id = ? AND user_id = ?"
    query_db(sql,(category_name, spending_limit,id,user_id,))
    get_db().commit()
    return redirect (url_for("view_categories"))

@app.route("/delete_category/<int:id>")
def delete_category(id):
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    user_id = user[0]
    sql = "DELETE FROM category WHERE id =? AND user_id = ?"
    query_db(sql,(id,user_id,))
    sql = "DELETE FROM expenses WHERE category_id =? AND user_id = ?"
    query_db(sql,(id,user_id,))
    get_db().commit()
    return redirect (url_for("view_categories"))


def parse_date(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return datetime.date.today().isoformat()
    try:
        return datetime.datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return datetime.date.today().isoformat()

@app.route("/view_expenses")
def view_expenses():
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    user_id = user[0]

    sql = "SELECT expenses.id, expenses.name, expenses.amount_spent, strftime('%Y-%m-%d', expenses.date) AS date, category.name AS category, expenses.category_id FROM expenses JOIN category ON expenses.category_id = category.id WHERE expenses.user_id = ?"
    expenses = query_db(sql, args=(user_id,))
    sql = "SELECT * FROM category WHERE user_id = ?"
    categories = query_db(sql, args=(user_id,))
    return render_template("expenses.html", expenses=expenses, categories=categories)

@app.route ("/add_expenses", methods = ["POST"])
def add_expenses():
    category_id = request.form['category_id']
    expenses_name = request.form['name']
    amount_spent = request.form['amount_spent']
    date = parse_date(request.form.get('date'))
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    user_id = user[0]
    sql = "SELECT name FROM category WHERE id = ? AND user_id = ?"
    category = query_db(sql, (category_id, user_id), one=True)
    if not category:
        flash('Selected category does not exist')
        return redirect(url_for('view_expenses'))
    category_name = category[0]
    sql = "INSERT INTO expenses (category_id, category_name, name, amount_spent, date, user_id) VALUES (?, ?, ?, ?, ?, ?)"
    query_db(sql, (category_id, category_name, expenses_name, amount_spent, date, user_id,))
    get_db().commit()
    return redirect(url_for("view_expenses"))

@app.route ("/edit_expenses/<int:id>", methods = ["POST"])
def edit_expenses(id):
    category_id = request.form['category_id']
    expenses_name = request.form['name']
    amount_spent = request.form['amount_spent']
    date = parse_date(request.form.get('date'))
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    user_id = user[0]
    sql = "SELECT name FROM category WHERE id = ? AND user_id = ?"
    category = query_db(sql, (category_id, user_id), one=True)
    if not category:
        flash('Selected category does not exist')
        return redirect(url_for('view_expenses'))
    category_name = category[0]
    sql = "UPDATE expenses SET category_id = ?, category_name = ?, name = ?, amount_spent = ?, date = ? WHERE id = ? AND user_id = ?"
    query_db(sql, (category_id, category_name, expenses_name, amount_spent, date, id, user_id,))
    get_db().commit()
    return redirect (url_for("view_expenses"))
    

@app.route("/delete_expenses/<int:id>")
def delete_expenses(id):
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    user_id = user[0]
    sql = "DELETE FROM expenses WHERE id =? AND user_id = ?"
    query_db(sql,(id,user_id,))
    get_db().commit()
    return redirect (url_for("view_expenses"))

@app.route("/editdate")
def edit_date():
    return redirect(url_for("view_expenses"))

        





if __name__ == "__main__":
    app.run(debug= True)