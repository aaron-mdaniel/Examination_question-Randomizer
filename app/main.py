import json
import random
from functools import wraps
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from app import db
from app.models import Exam, GeneratedPaper, GeneratedPaperQuestion, Question

main_bp = Blueprint("main", __name__)


def teacher_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.role != "teacher":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return render_template("index.html")


@main_bp.route("/dashboard")
@login_required
def dashboard():
    question_count = Question.query.count()
    exams = Exam.query.order_by(Exam.created_at.desc()).limit(10).all()
    return render_template("dashboard.html", question_count=question_count, exams=exams)


@main_bp.route("/questions")
@teacher_required
def questions():
    subject = request.args.get("subject", "").strip()
    query = Question.query
    if subject:
        query = query.filter(Question.subject.ilike(f"%{subject}%"))
    items = query.order_by(Question.created_at.desc()).all()
    return render_template("questions.html", questions=items, subject=subject)


@main_bp.route("/questions/new", methods=["GET", "POST"])
@teacher_required
def new_question():
    if request.method == "POST":
        form = request.form
        question_text = form.get("question_text", "").strip()
        options = [form.get(f"option_{letter.lower()}", "").strip() for letter in "ABCD"]
        correct = form.get("correct_option", "")
        marks_raw = form.get("marks", "1")
        if not question_text or any(not value for value in options):
            flash("Question text and all four options are required.", "danger")
            return render_template("question_form.html")
        if correct not in "ABCD":
            flash("Select the correct option.", "danger")
            return render_template("question_form.html")
        try:
            marks = int(marks_raw)
            if marks < 1:
                raise ValueError
        except ValueError:
            flash("Marks must be a positive whole number.", "danger")
            return render_template("question_form.html")
        item = Question(
            subject=form.get("subject", "").strip(),
            topic=form.get("topic", "General").strip() or "General",
            difficulty=form.get("difficulty", "medium"),
            question_text=question_text,
            option_a=options[0], option_b=options[1],
            option_c=options[2], option_d=options[3],
            correct_option=correct, marks=marks,
        )
        if not item.subject:
            flash("Subject is required.", "danger")
            return render_template("question_form.html")
        db.session.add(item)
        db.session.commit()
        flash("Question added to the question bank.", "success")
        return redirect(url_for("main.questions"))
    return render_template("question_form.html")


@main_bp.route("/exams/new", methods=["GET", "POST"])
@teacher_required
def new_exam():
    if request.method == "POST":
        form = request.form
        try:
            count = int(form.get("question_count", "10"))
            duration = int(form.get("duration_minutes", "30"))
            if count < 1 or duration < 1:
                raise ValueError
        except ValueError:
            flash("Question count and duration must be positive whole numbers.", "danger")
            return render_template("exam_form.html")
        title = form.get("title", "").strip()
        subject = form.get("subject", "").strip()
        difficulty = form.get("difficulty", "any")
        if not title or not subject:
            flash("Exam title and subject are required.", "danger")
            return render_template("exam_form.html")
        exam = Exam(
            title=title, subject=subject, question_count=count,
            duration_minutes=duration, difficulty=difficulty,
            created_by=current_user.id,
        )
        db.session.add(exam)
        db.session.commit()
        flash("Exam configuration created.", "success")
        return redirect(url_for("main.dashboard"))
    return render_template("exam_form.html")


@main_bp.route("/exams/<int:exam_id>/generate", methods=["POST"])
@teacher_required
def generate_paper(exam_id):
    exam = db.session.get(Exam, exam_id)
    if not exam:
        abort(404)
    query = Question.query.filter_by(subject=exam.subject)
    if exam.difficulty != "any":
        query = query.filter_by(difficulty=exam.difficulty)
    pool = query.all()
    if len(pool) < exam.question_count:
        flash(
            f"Not enough questions: this exam needs {exam.question_count}, "
            f"but only {len(pool)} match its subject/difficulty filters.",
            "danger",
        )
        return redirect(url_for("main.dashboard"))

    # Random sampling selects a combination without enumerating all combinations.
    selected = random.SystemRandom().sample(pool, exam.question_count)
    option_orders = {}
    question_ids = []
    for question in selected:
        question_ids.append(question.id)
        option_orders[str(question.id)] = random.SystemRandom().sample(["A", "B", "C", "D"], 4)

    paper = GeneratedPaper(
        exam_id=exam.id,
        question_ids_json=json.dumps(question_ids),
        option_orders_json=json.dumps(option_orders),
    )
    db.session.add(paper)
    db.session.flush()
    for position, question in enumerate(selected, start=1):
        db.session.add(GeneratedPaperQuestion(
            paper_id=paper.id, question_id=question.id, position=position
        ))
    db.session.commit()
    flash(f"Generated randomized paper #{paper.id}.", "success")
    return redirect(url_for("main.paper", paper_id=paper.id))


@main_bp.route("/papers/<int:paper_id>")
@teacher_required
def paper(paper_id):
    paper = db.session.get(GeneratedPaper, paper_id)
    if not paper:
        abort(404)
    ids = json.loads(paper.question_ids_json)
    orders = json.loads(paper.option_orders_json)
    questions_by_id = {q.id: q for q in Question.query.filter(Question.id.in_(ids)).all()}
    ordered_questions = [questions_by_id[qid] for qid in ids if qid in questions_by_id]
    return render_template("paper.html", paper=paper, questions=ordered_questions, orders=orders)
