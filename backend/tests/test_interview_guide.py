from app.experts import INTERVIEW_GUIDE_FILE
from app.interview_guide import load_questions


def test_loads_exactly_the_six_questions_from_the_case_pack():
    questions = load_questions(INTERVIEW_GUIDE_FILE)
    assert len(questions) == 6
    assert questions[0].startswith("How would you describe current adoption")
    assert "ROI" in questions[2]
