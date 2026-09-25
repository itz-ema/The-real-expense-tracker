
"Modules needed to build the app"
import math
import sqlite3
import datetime
from flask import Flask, render_template, url_for, g, request, redirect, flash, session
from werkzeug.security import generate_password_hash, check_password_hash



DATABASE = "database.db"
app = Flask(__name__)

app.config['SECRET_KEY'] = 'itsasecret'
#to protect user sessions

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
    #helps to make db querying easier and less bulky


ensure_schema()

def get_db():
    "Connecting the app to the database"
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

def query_db(query, args=(), one=False):
    "To easily make queries in the database"
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def parse_spending_limit(value):
    "setting boundaries for the spending limit "
    try:
        spending_limit = float(value)
        #spending limit can be a decimal
    except (TypeError, ValueError):
        return None
    return spending_limit if math.isfinite(spending_limit) and spending_limit >= 0 else None

def build_monthly_category_totals(expenses, month):
    "To build monthly category tools"
    totals = {}
    for expense in expenses:
        expense_date = expense[3] if len(expense) > 3 else ""
        category_name = expense[4] if len(expense) > 4 else ""
        if expense_date.startswith(month) and category_name:
            amount = float(expense[2] or 0)
            totals[category_name] = totals.get(category_name, 0.0) + amount
    return totals


def build_pie_chart_segments(totals):
    "Building the piechart that will hold the categoires by month"
    colors = ["#0d6efd", "#198754", "#dc3545", "#ffc107", "#6f42c1", "#20c997", "#fd7e14"]
    #identifying the different colours for different sectors of the pie chart
    if not totals:
        return []

    total_value = sum(totals.values())
    if total_value <= 0:
        return [] #if nothing has been inputted, the piechart will be blank

    radius = 70
    circumference = 2 * math.pi * radius
    offset = 0.0
    segments = []
    #defining how big the piechart will be
    #segments are left blank and will be determined by expense values

    for index, (name, amount) in enumerate(totals.items()):
        segment_length = circumference * (amount / total_value)
        segments.append({
            "name": name,
            "amount": round(amount, 2),
            "percent": round((amount / total_value) * 100, 1),
            "color": colors[index % len(colors)],
            "dasharray": f"{round(segment_length, 2)} {round(circumference - segment_length, 2)}",
            "dashoffset": round(-offset, 2),
        })
        offset += segment_length
        #the amount spent is summed and rounded up to 2dp
        #the percentage of that amount is taken, relative to the total amount spent for that month
        #

    return segments


@app.route("/") #this will be the homepage/dashboard of the app
def home():
    "Main homepage"
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    user_id = user[0]

    selected_month = request.args.get("month") or datetime.date.today().strftime("%Y-%m")

    # compute category totals for the selected month only
    sql = '''SELECT category.id, category.name, category.spending_limit,
            IFNULL(SUM(expenses.amount_spent), 0)
             AS total_amount_spent FROM category LEFT JOIN expenses ON category.id = expenses.category_id
                AND expenses.user_id = ?
                AND strftime('%Y-%m', expenses.date) = ?
            WHERE category.user_id = ?
            GROUP BY category.id'''
    categories = query_db(sql, args=(user_id, selected_month, user_id))

    monthly_sql = '''SELECT expenses.id, expenses.name, expenses.amount_spent,
                    strftime('%Y-%m-%d', expenses.date) AS date,
                    category.name AS category, expenses.category_id
                    FROM expenses
                    JOIN category ON expenses.category_id = category.id
                    WHERE expenses.user_id = ? AND strftime('%Y-%m', expenses.date) = ?'''
    monthly_expenses = query_db(monthly_sql, args=(user_id, selected_month))
    monthly_totals = build_monthly_category_totals(monthly_expenses, selected_month)
    pie_segments = build_pie_chart_segments(monthly_totals)

    get_db().commit()
    username = user[1]
    return render_template(
        "home.html",
        categories=categories,
        username=username,
        selected_month=selected_month,
        monthly_totals=monthly_totals,
        pie_segments=pie_segments,
    )

@app.route("/help") #this will be the route for the help page of the app
def help_iterable(): #help iterable is used to allow redifining a built in variable
    "To direct the user to the help page which provides information on how to use the app"
    return render_template("help.html")

@app.route("/login", methods=["GET", "POST"]) #This is the login page for the app
def login():
    "To create the login page fot users to access the app"
    if request.method == "POST":
        name = request.form["name"]
        password = request.form["password"]
        sql = "SELECT id, name, password FROM user WHERE name = ?"
        user = query_db(sql,args=(name,), one=True)

        if user and check_password_hash(user[2], password):
            session["user"] = user
            flash("Logged in successfully")
            #if both the user and password are accurate
            return redirect(url_for("home"))
        if user:
            if check_password_hash(user[2], password):
                #checking if the username and password match the ones that are in the database
                session['user']= user
                flash("Logged in successfully")
            else:
                flash('Password incorrect') #if the username exists but the password is wrong
        else:
            flash ('Username does not exist') #if the inputted username is not in the database
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    "To register the new users and put their details in the database"
    if request.method == "POST":
        name = request.form.get("name") or request.form.get("username")
        password = request.form.get("password")

        if not name or not password: #if both username and password field are left unfilled
            flash("Please enter both username and password")
            return render_template("register.html")
        existing = query_db("SELECT id FROM user WHERE name = ?", (name,), one=True)
        if existing: # To prevent duplicate usernames
            flash("Username is already taken")
            flash ("Please choose a different username")
            #user is required to use a username that is not already in the database
            return render_template("register.html")

        password_hash = generate_password_hash(password)
        #securely stores the password on the database
        sql = "INSERT INTO user (name, password) VALUES (?, ?)"
        #adds the new username and password into the database
        query_db(sql, (name, password_hash))
        get_db().commit()
        flash("Registration successful!")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/categories")
def view_categories():
    "To view the page where all the already made categoies will be displayed and more can be added"
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    user_id = user[0]
    sql = "SELECT * FROM category WHERE user_id = ?"
    #get already existing categories and matching parameters from database
    categories = query_db(sql, args=(user_id,))
    return render_template("categories.html", categories=categories)

@app.route ("/add_category", methods = ["POST"])
def add_category():
    "To add a new expense"
    category_name = request.form ['name']
    spending_limit = parse_spending_limit(request.form ['spending_limit'])
    if spending_limit is None:
        flash("Spending limit must be a non-negative number.")
        return redirect(url_for("view_categories"))
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    user_id = user[0]
    sql = "INSERT INTO category (name, spending_limit, user_id) VALUES (?, ?, ?)"
    #a new row is added to the database containing the category and corresponding data
    query_db(sql,(category_name, spending_limit, user_id,))
    get_db().commit()
    return redirect (url_for("view_categories"))

@app.route ("/edit_category/<int:id_iterable>", methods = ["POST"])
def edit_category(id_iterable):
    "To make edits to already created category"
    category_name = request.form ['name']
    spending_limit = parse_spending_limit(request.form ['spending_limit'])
    #spending limit must meet certain criteria
    if spending_limit is None:
        flash("Spending limit must be a non-negative number.")
        #spending limit is not allowed to be zero or lower
        return redirect(url_for("view_categories"))
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    user_id = user[0]
    sql = "UPDATE category SET name =?, spending_limit = ? WHERE id = ? AND user_id = ?"
    #the changes are added to the database and then displayed
    query_db(sql,(category_name, spending_limit,id_iterable,user_id,))
    get_db().commit()
    return redirect (url_for("view_categories"))

@app.route("/delete_category/<int:id_iterable>")
def delete_category(id_iterable):
    "to delete an already created category and its corresponding amount limit"
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    user_id = user[0]
    sql = "DELETE FROM category WHERE id =? AND user_id = ?"
    #removes the whole row from the database
    query_db(sql,(id_iterable,user_id,))
    sql = "DELETE FROM expenses WHERE category_id =? AND user_id = ?"
    #removes any expenses tied to that category from the expense page
    query_db(sql,(id_iterable,user_id,))
    get_db().commit()
    return redirect (url_for("view_categories"))


def parse_date(value: str) -> str:
    "Converting the string into date and time"
    value = (value or "").strip()
    if not value:
        return datetime.date.today().isoformat()
    try:
        return datetime.datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return datetime.date.today().isoformat()

@app.route("/view_expenses")
def view_expenses():
    "To view the whole expense page"
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    user_id = user[0]
    sql = """SELECT expenses.id, expenses.name, expenses.amount_spent,
                strftime('%Y-%m-%d', expenses.date)
                AS date, category.name AS category, expenses.category_id FROM expenses 
                JOIN category ON expenses.category_id = category.id WHERE expenses.user_id = ?"""
    #everything needed for the expense page is gotten from the database
    #the expense database is joined to the category database, to link
    #category names, and match the category id to the expense.category_id
    expenses = query_db(sql, args=(user_id,))
    sql = "SELECT * FROM category WHERE user_id = ?"
    categories = query_db(sql, args=(user_id,))
    return render_template("expenses.html", expenses=expenses, categories=categories)

@app.route ("/add_expenses", methods = ["POST"])
def add_expenses():
    "To add a new expense"
    category_id = request.form.get('category_id')
    expenses_name = request.form.get('name')
    amount_spent = request.form.get('amount_spent')
    date = parse_date(request.form.get('date'))
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    user_id = user[0]

    try:
        category_id = int(category_id)
    except (TypeError, ValueError):
        flash('Please select a valid category')
        return redirect(url_for('view_expenses'))

    try:
        amount_spent = float(amount_spent)
    except (TypeError, ValueError):
        flash('Amount spent must be a number')
        return redirect(url_for('view_expenses'))
        #if the user inputs a value that is not a number into the amount spent,
        # the app wil flash "amount must be a number".

    sql = "SELECT id FROM category WHERE id = ? AND user_id = ?"
    category = query_db(sql, (category_id, user_id), one=True)
    if not category:
        flash('Selected category does not exist')
        return redirect(url_for('view_expenses'))

    sql = """INSERT INTO expenses (category_id,
      name, amount_spent, date, user_id) VALUES (?, ?, ?, ?, ?)"""
    #the new expense and corresponding information is added into the database
    query_db(sql, (category_id, expenses_name, amount_spent, date, user_id,))
    get_db().commit()
    return redirect(url_for("view_expenses"))

@app.route ("/edit_expenses/<int:id_iterable>", methods = ["POST"])
def edit_expenses(id_iterable):
    "To make edits to already created expenses"
    category_id = request.form.get('category_id')
    expenses_name = request.form.get('name')
    amount_spent = request.form.get('amount_spent')
    date = parse_date(request.form.get('date'))
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    user_id = user[0]

    try:
        category_id = int(category_id)
    except (TypeError, ValueError):
        flash('Please select a valid category')
        #this prevents the user from not selecting any category at all
        return redirect(url_for('view_expenses'))

    try:
        #using the try funtion to prevent crashing and errors if the parameters are not met
        amount_spent = float(amount_spent)
    except (TypeError, ValueError):
        flash('Amount spent must be a number')
        #if the user inputs a value that is not a number into the amount spent,
        # the app wil flash "amount must be a number".
        return redirect(url_for('view_expenses'))

    sql = "SELECT id FROM category WHERE id = ? AND user_id = ?"
    category = query_db(sql, (category_id, user_id), one=True)
    if not category:
        flash('Selected category does not exist')
        return redirect(url_for('view_expenses'))

    sql = """UPDATE expenses SET category_id = ?, name = ?,
             amount_spent = ?, date = ? WHERE id = ? AND user_id = ?"""
    #inouts the changed expense into the database
    query_db(sql, (category_id, expenses_name, amount_spent, date, id_iterable, user_id,))
    get_db().commit()
    return redirect (url_for("view_expenses"))

@app.route("/delete_expenses/<int:id_iterable>")
def delete_expenses(id_iterable):
    "To delete expenses that are no longer needed"
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    user_id = user[0]
    sql = "DELETE FROM expenses WHERE id =? AND user_id = ?"
    #deletes the expenses from the database
    #the deleted expenses will no longer be displayed on expenses page
    query_db(sql,(id_iterable,user_id,))
    get_db().commit()
    return redirect (url_for("view_expenses"))

@app.route("/editdate")
def edit_date():
    "To edit the day of an already created expense"
    return redirect(url_for("view_expenses"))

if __name__ == "__main__":
    app.run(debug= True)
