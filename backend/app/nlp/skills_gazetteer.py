"""Small bundled list of named technologies, used as a Phase 3 fallback
signal for skills mentioned in Experience/Project prose (not just listed
in a dedicated Skills section).

This is a placeholder, not the real skill taxonomy — Phase 5 replaces it
with the `skills`/`skill_aliases` tables seeded from O*NET + ESCO + a
curated set (docs/ARCHITECTURE.md §7), including the disambiguation rules
(Java vs JavaScript, React vs React Native) a flat list like this one
cannot express.

Deliberately limited to specific named technologies (proper nouns), not
generic words ("API", "cloud", "testing") that would false-positive
against ordinary prose bullets.
"""
GAZETTEER: list[str] = [
    # Languages
    "Python", "Java", "JavaScript", "TypeScript", "Go", "Rust", "C++", "C#",
    "Ruby", "PHP", "Swift", "Kotlin", "Scala",
    # Web / frameworks
    "React", "Angular", "Vue", "Node.js", "Django", "Flask", "FastAPI",
    "Spring Boot", "Spring", "Rails", ".NET", "GraphQL", "gRPC",
    # Data / ML
    "PyTorch", "TensorFlow", "scikit-learn", "Pandas", "NumPy", "Spark",
    "Hadoop", "Airflow",
    # Databases
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch", "SQLite",
    "Cassandra", "DynamoDB",
    # Infra / cloud / devops
    "AWS", "GCP", "Azure", "Docker", "Kubernetes", "Terraform", "Jenkins",
    "GitLab", "GitHub Actions", "Kafka", "RabbitMQ", "Microservices",
    "CI/CD", "Linux", "Bash",
    # Other
    "SQL", "Agile", "Scrum",
]
