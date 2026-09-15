"""Regression tests for boundary-aware grounding of parsed resume facts."""

from app.services.grounding import ground_parsed_resume, is_source_supported


class TestIsSourceSupported:
    def test_rejects_term_embedded_in_longer_word(self):
        assert not is_source_supported("Java", "Built JavaScript applications")
        assert not is_source_supported("C", "Cloud systems")
        assert not is_source_supported("AI", "Sat in a chair all day")

    def test_accepts_exact_whole_term(self):
        assert is_source_supported("Java", "Strong Java backend experience")
        assert is_source_supported("Python", "python")

    def test_accepts_case_insensitive_unicode(self):
        assert is_source_supported("café", "Worked at a CAFÉ")

    def test_accepts_multi_word_phrases(self):
        assert is_source_supported(
            "machine learning", "Led machine learning platform team"
        )
        assert not is_source_supported(
            "machine learning", "Led machine washing platform team"
        )

    def test_accepts_technical_tokens(self):
        assert is_source_supported("C++", "Systems engineer skilled in C++ and Rust")
        assert is_source_supported("C#", "Built C# services")
        assert is_source_supported(".NET", "Shipped .NET web apps")
        assert is_source_supported("CI/CD", "Owned CI/CD pipelines")
        assert is_source_supported("problem-solving", "Strong problem-solving skills")

    def test_rejects_technical_token_inside_unrelated_word(self):
        assert not is_source_supported("C#", "Built C sharp services")
        assert not is_source_supported("C++", "Graded C plus plus coursework")


class TestGroundParsedResume:
    def _source(self) -> str:
        return (
            "Senior Software Engineer with 8 years of experience. "
            "Skilled in Python, and Kubernetes at Acme Corp. "
            "Built JavaScript applications for the web team. "
            "Sat in a chair all day. Led machine learning platform team. "
            "Worked with C++ and CI/CD pipelines. Shipped .NET web apps. "
            "Strong problem-solving skills."
        )

    def test_drops_skill_only_present_inside_longer_word(self):
        parsed = {"skills": ["Java", "Python", "AI"]}
        grounded = ground_parsed_resume(parsed, self._source())
        assert "Python" in grounded["skills"]
        assert "Java" not in grounded["skills"]  # only JavaScript is in the source
        assert "AI" not in grounded["skills"]  # only inside "chair"

    def test_keeps_whole_term_skills(self):
        parsed = {"skills": ["Kubernetes", "C++", ".NET", "CI/CD"]}
        grounded = ground_parsed_resume(parsed, self._source())
        assert grounded["skills"] == ["Kubernetes", "C++", ".NET", "CI/CD"]

    def test_keeps_multi_word_phrase_skills(self):
        grounded = ground_parsed_resume({"skills": ["machine learning"]}, self._source())
        assert grounded["skills"] == ["machine learning"]

    def test_rejects_negated_resume_evidence(self):
        source = "Skills: Python, Kubernetes. No Java experience. Not familiar with Rust."
        grounded = ground_parsed_resume(
            {"skills": ["Python", "Java", "Rust"]}, source
        )
        assert grounded["skills"] == ["Python"]
