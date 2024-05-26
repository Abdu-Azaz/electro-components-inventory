from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pandas as pd
import csv
import io

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
app.config['SECRET_KEY'] = 'secret'
db = SQLAlchemy(app)
# csrf = CSRFProtect(app)


class Component(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    location = db.Column(db.String(100), nullable=False)
    date_added = db.Column(db.DateTime, default=datetime.utcnow)
    date_removed = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.String(200), nullable=True)
    out = db.Column(db.Integer, nullable=True, default=0)

    def __repr__(self):
        return f'<Component {self.name}>'

class BorrowedComponent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    component_id = db.Column(db.Integer, db.ForeignKey('component.id'), nullable=False)
    borrower_name = db.Column(db.String(100), nullable=False)
    borrowed_quantity = db.Column(db.Integer, nullable=False)
    borrowed_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    returned_date = db.Column(db.DateTime, nullable=True)

    component = db.relationship('Component', backref=db.backref('borrowed_components', lazy=True))

    def __repr__(self):
        return f'<BorrowedComponent {self.borrower_name} borrowed {self.borrowed_quantity} of {self.component_id}>'
@app.route('/')
def index():
    components = Component.query.all()
    borrowed_components = BorrowedComponent.query.all()
    return render_template('index.html', components=components, borrowed_components=borrowed_components)

@app.route('/clear', methods=['POST'])
def clear():
    # Find all borrowed components that have been returned
    returned_borrowed_components = BorrowedComponent.query.filter(BorrowedComponent.returned_date.isnot(None)).all()

    for borrowed in returned_borrowed_components:
        db.session.delete(borrowed)

    db.session.commit()

    flash('Cleared history of returned borrowed components.')
    return redirect(url_for('index'))


@app.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        print("Hello")
        print(request.form)
        name = request.form['name']
        quantity = request.form['quantity']
        location = request.form['location']
        category = request.form['category']
        notes = request.form['notes']

        new_component = Component(name=name, category=category, quantity=quantity, location=location, notes=notes)
        db.session.add(new_component)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('add.html')

@app.route('/update/<int:id>', methods=['GET', 'POST'])
def update(id):
    component = Component.query.get_or_404(id)
    if request.method == 'POST':
        component.name = request.form['name']
        component.category = request.form['category']
        component.quantity = request.form['quantity']
        component.location = request.form['location']
        component.notes = request.form['notes']
        if component.quantity == 0:
            component.date_removed = datetime.utcnow()
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('update.html', component=component)

@app.route('/delete/<int:id>')
def delete(id):
    component = Component.query.get_or_404(id)
    db.session.delete(component)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/return/<int:borrowed_id>', methods=['GET', 'POST'])
def return_component(borrowed_id):
    borrowed_component = BorrowedComponent.query.get_or_404(borrowed_id)
    if request.method == 'POST':
        borrowed_component.returned_date = datetime.utcnow()
        borrowed_component.component.out -= borrowed_component.borrowed_quantity
        db.session.commit()
        flash('Component returned successfully!')
        return redirect(url_for('index'))
    return render_template('return.html', borrowed_component=borrowed_component)


@app.route('/borrow/<int:component_id>', methods=['GET', 'POST'])
def borrow(component_id):
    component = Component.query.get_or_404(component_id)
    if request.method == 'POST':
        borrower_name = request.form['borrower_name']
        borrowed_quantity = int(request.form['borrowed_quantity'])
        if borrowed_quantity > (component.quantity - component.out):
            flash('Not enough components available.')
            return redirect(request.url)
        borrowed_component = BorrowedComponent(
            component_id=component.id,
            borrower_name=borrower_name,
            borrowed_quantity=borrowed_quantity
        )
        component.out += borrowed_quantity
        db.session.add(borrowed_component)
        db.session.commit()
        flash('Component borrowed successfully!')
        return redirect(url_for('index'))
    return render_template('borrow.html', component=component)


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and file.filename.endswith('.xlsx'):
            df = pd.read_excel(file)
            for index, row in df.iterrows():
                new_component = Component(
                    name=row['name'],
                    category=row['category'],
                    quantity=row['quantity'],
                    location=row['location'],
                    notes=row.get('notes', '')
                )
                db.session.add(new_component)
            db.session.commit()
            flash('Components added successfully!')
            return redirect(url_for('index'))
        else:
            flash('Invalid file format. Please upload an XLSX file.')
            return redirect(request.url)
    return render_template('upload.html')



@app.route('/export_csv')
def export_csv():
    components = Component.query.all()
    
    # Use StringIO to create a string buffer to write to
    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    
    # Write CSV headers
    writer.writerow(['ID', 'Name', 'Quantity', 'Category', 'Location', 'Notes', 'Out'])
    
    # Write data rows
    for component in components:
        writer.writerow([component.id, component.name, component.quantity, component.category, component.location, component.notes, component.out])
    
    # Create a response with the CSV data
    response = send_file(
        io.BytesIO(csv_buffer.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='components.csv'
    )
    
    return response

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
