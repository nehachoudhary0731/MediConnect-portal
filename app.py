import os
import sys
from datetime import datetime
from flask import Flask, render_template, url_for, flash, redirect, request, abort
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, current_user, login_user, logout_user, login_required
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SelectField, TextAreaField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', '1234abcd')

# Database configuration
db_user = os.getenv('DB_USER', 'root')
db_password = os.getenv('DB_PASSWORD', '')
db_host = os.getenv('DB_HOST', 'localhost')
db_name = os.getenv('DB_NAME', 'medical_portal')

app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql://{db_user}:{db_password}@{db_host}/{db_name}'
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2MB file limit
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

# Database Models
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(10), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    address_line1 = db.Column(db.String(100))
    city = db.Column(db.String(50))
    state = db.Column(db.String(50))
    pincode = db.Column(db.String(10))
    profile_picture = db.Column(db.String(100))
    posts = db.relationship('BlogPost', backref='author', lazy=True)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    posts = db.relationship('BlogPost', backref='cat', lazy=True)

class BlogPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    image = db.Column(db.String(100))
    content = db.Column(db.Text, nullable=False)
    summary = db.Column(db.String(200))
    is_draft = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# Forms
class RegistrationForm(FlaskForm):
    role = SelectField('Role', choices=[('doctor', 'Doctor'), ('patient', 'Patient')], validators=[DataRequired()])
    first_name = StringField('First Name', validators=[DataRequired(), Length(min=2, max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(min=2, max=50)])
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    address_line1 = StringField('Address Line 1', validators=[DataRequired()])
    city = StringField('City', validators=[DataRequired()])
    state = StringField('State', validators=[DataRequired(), Length(max=50)])
    pincode = StringField('Zip Code', validators=[DataRequired(), Length(min=5, max=10)])
    profile_picture = FileField('Profile Picture', validators=[FileAllowed(['jpg', 'png'])])
    submit = SubmitField('Sign Up')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('That username is taken. Please choose a different one.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('That email is taken. Please choose a different one.')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    role = SelectField('Role', choices=[('doctor', 'Doctor'), ('patient', 'Patient')], validators=[DataRequired()])
    submit = SubmitField('Login')

class BlogPostForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(max=100)])
    image = FileField('Blog Image', validators=[FileAllowed(['jpg', 'png', 'jpeg'])])
    category = SelectField('Category', coerce=int, validators=[DataRequired()])
    summary = TextAreaField('Summary', validators=[DataRequired(), Length(max=200)])
    content = TextAreaField('Content', validators=[DataRequired()])
    is_draft = BooleanField('Save as Draft')
    submit = SubmitField('Publish')

# Flask-Login user loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            hashed_password = generate_password_hash(form.password.data)
            profile_pic_filename = None
            
            if form.profile_picture.data:
                filename = secure_filename(form.profile_picture.data.filename)
                profile_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'profile_pics')
                
                # Create directory if not exists
                if not os.path.exists(profile_dir):
                    os.makedirs(profile_dir)
                
                file_path = os.path.join(profile_dir, filename)
                form.profile_picture.data.save(file_path)
                profile_pic_filename = f'profile_pics/{filename}'
            
            user = User(
                username=form.username.data,
                email=form.email.data,
                password=hashed_password,
                role=form.role.data,
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                address_line1=form.address_line1.data,
                city=form.city.data,
                state=form.state.data,
                pincode=form.pincode.data,
                profile_picture=profile_pic_filename
            )
            
            db.session.add(user)
            db.session.commit()
            flash('Your account has been created! You can now log in', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating account: {str(e)}', 'danger')
    
    # Show form validation errors
    if form.errors:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", 'danger')
    
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password, form.password.data) and user.role == form.role.data:
            login_user(user)
            next_page = request.args.get('next')
            if user.role == 'doctor':
                return redirect(next_page or url_for('doctors_dashboard'))
            else:
                return redirect(next_page or url_for('patients_dashboard'))
        else:
            flash('Login Unsuccessful. Please check username, password and role', 'danger')
    
    # Show form validation errors
    if form.errors:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", 'danger')
    
    return render_template('login.html', form=form)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/doctors_dashboard')
@login_required
def doctors_dashboard():
    if current_user.role != 'doctor':
        abort(403)
    return render_template('doctors_dashboard.html', user=current_user)

@app.route('/patients_dashboard')
@login_required
def patients_dashboard():
    if current_user.role != 'patient':
        abort(403)
    return render_template('patients_dashboard.html', user=current_user)

# Blog routes
@app.route('/blog/create', methods=['GET', 'POST'])
@login_required
def create_blog():
    if current_user.role != 'doctor':
        abort(403)
    
    form = BlogPostForm()
    form.category.choices = [(c.id, c.name) for c in Category.query.all()]
    
    if form.validate_on_submit():
        try:
            image_filename = None
            if form.image.data:
                filename = secure_filename(form.image.data.filename)
                blog_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'blog_images')
                
                # Create directory if not exists
                if not os.path.exists(blog_dir):
                    os.makedirs(blog_dir)
                
                file_path = os.path.join(blog_dir, filename)
                form.image.data.save(file_path)
                image_filename = f'blog_images/{filename}'
                
            post = BlogPost(
                title=form.title.data,
                image=image_filename,
                summary=form.summary.data,
                content=form.content.data,
                is_draft=form.is_draft.data,
                category_id=form.category.data,
                doctor_id=current_user.id
            )
            
            db.session.add(post)
            db.session.commit()
            flash('Blog post created successfully!', 'success')
            return redirect(url_for('my_posts'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating blog post: {str(e)}', 'danger')
    
    return render_template('create_blog.html', form=form, title='Create Post')

@app.route('/blog/my_posts')
@login_required
def my_posts():
    if current_user.role != 'doctor':
        abort(403)
    
    posts = BlogPost.query.filter_by(doctor_id=current_user.id).all()
    return render_template('my_blog_posts.html', posts=posts, title='My Posts')

@app.route('/blog')
@login_required
def blog_home():
    if current_user.role != 'patient':
        abort(403)
    
    categories = Category.query.all()
    category_posts = {}
    
    for category in categories:
        posts = BlogPost.query.filter_by(
            category_id=category.id,
            is_draft=False
        ).all()
        category_posts[category] = posts
    
    return render_template('blog_posts.html', category_posts=category_posts, title='Health Blog')

# Database Initialization
def initialize_database():
    try:
        with app.app_context():
            # Create upload directories
            upload_dirs = [
                app.config['UPLOAD_FOLDER'],
                os.path.join(app.config['UPLOAD_FOLDER'], 'profile_pics'),
                os.path.join(app.config['UPLOAD_FOLDER'], 'blog_images')
            ]
            
            for directory in upload_dirs:
                if not os.path.exists(directory):
                    os.makedirs(directory)
            
            # Create database tables
            db.create_all()
            print("Database tables created")
            
            # Create default categories
            categories = ['Mental Health', 'Heart Disease', 'Covid19', 'Immunization']
            for cat_name in categories:
                if not Category.query.filter_by(name=cat_name).first():
                    category = Category(name=cat_name)
                    db.session.add(category)
            db.session.commit()
            print("Database initialized with default categories")
    except Exception as e:
        print(f"Error initializing database: {str(e)}")
        sys.exit(1)

# Initialize the application
if __name__ == '__main__':
    print("Starting Medical Portal Application...")
    print(f"Using database: {app.config['SQLALCHEMY_DATABASE_URI']}")
    initialize_database()
    app.run(debug=True)