import json
import random
from functools import wraps
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from app import db
from app.models import Exam, ExamBlueprint, GeneratedPaper, GeneratedPaperQuestion, Question

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
    search_text = request.args.get("q", "").strip()
    subject = request.args.get("subject", "").strip()
    topic = request.args.get("topic", "").strip()
    difficulty = request.args.get("difficulty", "").strip()
    query = Question.query
    if search_text:
        query = query.filter(Question.question_text.ilike(f"%{search_text}%"))
    if subject:
        query = query.filter(Question.subject.ilike(f"%{subject}%"))
    if topic:
        query = query.filter(Question.topic.ilike(f"%{topic}%"))
    if difficulty in {"easy", "medium", "hard"}:
        query = query.filter(Question.difficulty == difficulty)
    items = query.order_by(Question.created_at.desc()).all()
    subjects = [r[0] for r in db.session.query(Question.subject).distinct().order_by(Question.subject).all()]
    topics = [r[0] for r in db.session.query(Question.topic).distinct().order_by(Question.topic).all()]
    return render_template("questions.html", questions=items, search_text=search_text,
        subject=subject, topic=topic, difficulty=difficulty, subjects=subjects, topics=topics)

def read_question_form(form):
    subject = form.get("subject", "").strip()
    topic = form.get("topic", "General").strip() or "General"
    difficulty = form.get("difficulty", "medium").strip().lower()
    question_text = form.get("question_text", "").strip()
    options = [form.get("option_" + letter.lower(), "").strip() for letter in "ABCD"]
    correct = form.get("correct_option", "").strip().upper()
    if not subject: return None, "Subject is required."
    if not question_text: return None, "Question text is required."
    if any(not option for option in options): return None, "All four options are required."
    if correct not in {"A", "B", "C", "D"}: return None, "Select a valid correct option."
    if difficulty not in {"easy", "medium", "hard"}: return None, "Select a valid difficulty."
    try:
        marks = int(form.get("marks", "1"))
        if marks < 1: raise ValueError
    except (TypeError, ValueError):
        return None, "Marks must be a positive whole number."
    return dict(subject=subject, topic=topic, difficulty=difficulty, question_text=question_text,
        option_a=options[0], option_b=options[1], option_c=options[2], option_d=options[3],
        correct_option=correct, marks=marks), None

@main_bp.route("/questions/new", methods=["GET", "POST"])
@teacher_required
def new_question():
    if request.method == "POST":
        values, error = read_question_form(request.form)
        if error:
            flash(error, "danger")
            return render_template("question_form.html", question=request.form, editing=False)
        db.session.add(Question(**values))
        db.session.commit()
        flash("Question added to the question bank.", "success")
        return redirect(url_for("main.questions"))
    return render_template("question_form.html", question=None, editing=False)

@main_bp.route("/questions/<int:question_id>/edit", methods=["GET", "POST"])
@teacher_required
def edit_question(question_id):
    item = db.session.get(Question, question_id)
    if item is None: abort(404)
    if request.method == "POST":
        values, error = read_question_form(request.form)
        if error:
            flash(error, "danger")
            return render_template("question_form.html", question=request.form, editing=True, question_id=item.id)
        for field, value in values.items():
            setattr(item, field, value)
        db.session.commit()
        flash(f"Question #{item.id} updated.", "success")
        return redirect(url_for("main.questions"))
    return render_template("question_form.html", question=item, editing=True, question_id=item.id)

@main_bp.route("/questions/<int:question_id>/delete", methods=["POST"])
@teacher_required
def delete_question(question_id):
    item = db.session.get(Question, question_id)
    if item is None: abort(404)
    # Preserve generated-paper history: don't delete questions already used in a paper.
    used = GeneratedPaperQuestion.query.filter_by(question_id=item.id).first()
    if used:
        flash("This question is already used in a generated paper and cannot be deleted. You may edit it for future exams.", "warning")
        return redirect(url_for("main.questions"))
    db.session.delete(item)
    db.session.commit()
    flash(f"Question #{question_id} deleted.", "success")
    return redirect(url_for("main.questions"))

@main_bp.route("/exams/new", methods=["GET", "POST"])
@teacher_required
def new_exam():
    if request.method == "POST":
        form = request.form
        try:
            count = int(form.get("question_count", "10"))
            duration = int(form.get("duration_minutes", "30"))
            if count < 1 or duration < 1: raise ValueError
        except ValueError:
            flash("Question count and duration must be positive whole numbers.", "danger")
            return render_template("exam_form.html")
        title, subject = form.get("title", "").strip(), form.get("subject", "").strip()
        difficulty = form.get("difficulty", "any")
        if not title or not subject:
            flash("Exam title and subject are required.", "danger")
            return render_template("exam_form.html")
        db.session.add(Exam(title=title, subject=subject, question_count=count,
            duration_minutes=duration, difficulty=difficulty, created_by=current_user.id))
        db.session.commit()
        flash("Exam configuration created.", "success")
        return redirect(url_for("main.dashboard"))
    return render_template("exam_form.html")


@main_bp.route("/exams/<int:exam_id>/blueprint", methods=["GET", "POST"])
@teacher_required
def exam_blueprint(exam_id):
    exam = db.session.get(Exam, exam_id)

    if exam is None:
        abort(404)

    blueprint = ExamBlueprint.query.filter_by(
        exam_id=exam.id
    ).first()

    if request.method == "POST":
        topic_counts = {}

        for line in request.form.get("topic_counts", "").splitlines():
            line = line.strip()

            if not line:
                continue

            if ":" not in line:
                flash("Use the format Topic: count.", "danger")
                return redirect(
                    url_for("main.exam_blueprint", exam_id=exam.id)
                )

            topic, count_text = line.rsplit(":", 1)

            try:
                count = int(count_text.strip())
                if not topic.strip() or count < 1:
                    raise ValueError
            except ValueError:
                flash(
                    "Each topic needs a name and a positive count.",
                    "danger"
                )
                return redirect(
                    url_for("main.exam_blueprint", exam_id=exam.id)
                )

            topic = topic.strip()

            if topic in topic_counts:
                flash(f"Duplicate topic: {topic}", "danger")
                return redirect(
                    url_for("main.exam_blueprint", exam_id=exam.id)
                )

            topic_counts[topic] = count

        try:
            difficulty_counts = {
                level: int(request.form.get(level + "_count", "0"))
                for level in ("easy", "medium", "hard")
            }

            if any(value < 0 for value in difficulty_counts.values()):
                raise ValueError
        except ValueError:
            flash("Difficulty counts must be non-negative integers.", "danger")
            return redirect(
                url_for("main.exam_blueprint", exam_id=exam.id)
            )

        if not topic_counts:
            flash("Enter at least one topic.", "danger")
        elif sum(topic_counts.values()) != exam.question_count:
            flash(
                f"Topic counts must total {exam.question_count}.",
                "danger"
            )
        elif sum(difficulty_counts.values()) != exam.question_count:
            flash(
                f"Difficulty counts must total {exam.question_count}.",
                "danger"
            )
        else:
            available_topics = {
                row[0]
                for row in db.session.query(Question.topic)
                .filter_by(subject=exam.subject)
                .distinct()
                .all()
            }

            unknown = set(topic_counts) - available_topics

            if unknown:
                flash(
                    "Unknown topics for this subject: "
                    + ", ".join(sorted(unknown)),
                    "danger"
                )
            else:
                if blueprint is None:
                    blueprint = ExamBlueprint(exam_id=exam.id)
                    db.session.add(blueprint)

                blueprint.topic_counts_json = json.dumps(topic_counts)
                blueprint.difficulty_counts_json = json.dumps(
                    difficulty_counts
                )

                db.session.commit()
                flash("Exam blueprint saved.", "success")

                return redirect(url_for("main.dashboard"))

        return redirect(
            url_for("main.exam_blueprint", exam_id=exam.id)
        )

    topic_counts = (
        json.loads(blueprint.topic_counts_json)
        if blueprint else {}
    )

    difficulty_counts = (
        json.loads(blueprint.difficulty_counts_json)
        if blueprint else {"easy": 0, "medium": 0, "hard": 0}
    )

    return render_template(
        "blueprint.html",
        exam=exam,
        topic_counts=topic_counts,
        difficulty_counts=difficulty_counts
    )

@main_bp.route("/exams/<int:exam_id>/generate", methods=["POST"])
@teacher_required
def generate_paper(exam_id):
    exam = db.session.get(Exam, exam_id)
    if not exam: abort(404)
    query = Question.query.filter_by(subject=exam.subject)
    if exam.difficulty != "any": query = query.filter_by(difficulty=exam.difficulty)
    pool = query.all()
    if len(pool) < exam.question_count:
        flash(f"Not enough questions: this exam needs {exam.question_count}, but only {len(pool)} match its filters.", "danger")
        return redirect(url_for("main.dashboard"))
    rng = random.SystemRandom()
    selected = rng.sample(pool, exam.question_count)
    ids, option_orders = [], {}
    for question in selected:
        ids.append(question.id)
        option_orders[str(question.id)] = rng.sample(["A", "B", "C", "D"], 4)
    paper = GeneratedPaper(exam_id=exam.id, question_ids_json=json.dumps(ids),
        option_orders_json=json.dumps(option_orders))
    db.session.add(paper)
    db.session.flush()
    for position, question in enumerate(selected, start=1):
        db.session.add(GeneratedPaperQuestion(paper_id=paper.id, question_id=question.id, position=position))
    db.session.commit()
    flash(f"Generated randomized paper #{paper.id}.", "success")
    return redirect(url_for("main.paper", paper_id=paper.id))

@main_bp.route("/papers/<int:paper_id>")
@teacher_required
def paper(paper_id):
    paper = db.session.get(GeneratedPaper, paper_id)
    if not paper: abort(404)
    ids = json.loads(paper.question_ids_json)
    orders = json.loads(paper.option_orders_json)
    by_id = {q.id: q for q in Question.query.filter(Question.id.in_(ids)).all()}
    ordered = [by_id[qid] for qid in ids if qid in by_id]
    return render_template("paper.html", paper=paper, questions=ordered, orders=orders)
