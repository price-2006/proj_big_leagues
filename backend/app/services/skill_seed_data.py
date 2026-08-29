"""Internal curated skill seed data (Phase 5) — `source='internal'` rows.

Expands Phase 3/4's flat GAZETTEER list (app/nlp/skills_gazetteer.py) into
a real taxonomy structure: categories, explicit alias variants, and
disambiguation pairs — exactly what a flat list of strings can't express,
which is the whole reason this phase exists.
"""
from dataclasses import dataclass, field


@dataclass
class SeedSkill:
    canonical_name: str
    category: str
    aliases: list[str] = field(default_factory=list)


INTERNAL_SKILLS: list[SeedSkill] = [
    # Languages
    SeedSkill("Python", "programming_language", ["python programming", "python3"]),
    SeedSkill("JavaScript", "programming_language", ["js", "ecmascript"]),
    SeedSkill("TypeScript", "programming_language", ["ts"]),
    SeedSkill("Java", "programming_language", ["oracle java", "core java"]),
    SeedSkill("C++", "programming_language", ["cpp", "c plus plus"]),
    SeedSkill("C#", "programming_language", ["csharp", "c sharp"]),
    SeedSkill("Go", "programming_language", ["golang"]),
    SeedSkill("Rust", "programming_language", []),
    SeedSkill("Ruby", "programming_language", []),
    SeedSkill("PHP", "programming_language", []),
    SeedSkill("Swift", "programming_language", []),
    SeedSkill("Kotlin", "programming_language", []),
    SeedSkill("Scala", "programming_language", []),
    SeedSkill("SQL", "programming_language", ["structured query language"]),
    # Web / app frameworks
    SeedSkill("React", "framework", ["react.js", "reactjs"]),
    SeedSkill("React Native", "framework", []),
    SeedSkill("Angular", "framework", ["angular2", "angular 2+"]),
    SeedSkill("AngularJS", "framework", ["angular.js", "angular 1"]),
    SeedSkill("Vue.js", "framework", ["vue", "vuejs"]),
    SeedSkill("Node.js", "framework", ["nodejs", "node"]),
    SeedSkill("Django", "framework", []),
    SeedSkill("Flask", "framework", []),
    SeedSkill("FastAPI", "framework", []),
    SeedSkill("Spring Boot", "framework", ["springboot"]),
    SeedSkill("Spring", "framework", ["spring framework"]),
    SeedSkill("Ruby on Rails", "framework", ["rails"]),
    SeedSkill(".NET", "framework", ["dotnet", "microsoft .net framework", "asp.net"]),
    SeedSkill("GraphQL", "framework", []),
    SeedSkill("gRPC", "framework", []),
    # ML / data
    SeedSkill("PyTorch", "ml_framework", []),
    SeedSkill("TensorFlow", "ml_framework", []),
    SeedSkill("scikit-learn", "ml_framework", ["sklearn"]),
    SeedSkill("Pandas", "ml_framework", []),
    SeedSkill("NumPy", "ml_framework", []),
    SeedSkill("Apache Spark", "data_infra", ["spark", "pyspark"]),
    SeedSkill("Apache Hadoop", "data_infra", ["hadoop"]),
    SeedSkill("Apache Airflow", "data_infra", ["airflow"]),
    SeedSkill("Apache Kafka", "data_infra", ["kafka"]),
    # Databases
    SeedSkill("PostgreSQL", "database", ["postgres"]),
    SeedSkill("MySQL", "database", []),
    SeedSkill("MongoDB", "database", ["mongo"]),
    SeedSkill("Redis", "database", []),
    SeedSkill("Elasticsearch", "database", []),
    SeedSkill("SQLite", "database", []),
    SeedSkill("Cassandra", "database", ["apache cassandra"]),
    SeedSkill("DynamoDB", "database", ["amazon dynamodb"]),
    # Cloud / devops
    SeedSkill("AWS", "cloud", ["amazon web services"]),
    SeedSkill("GCP", "cloud", ["google cloud platform", "google cloud"]),
    SeedSkill("Azure", "cloud", ["microsoft azure"]),
    SeedSkill("Docker", "devops", []),
    SeedSkill("Kubernetes", "devops", ["k8s"]),
    SeedSkill("Terraform", "devops", []),
    SeedSkill("Jenkins", "devops", []),
    SeedSkill("Ansible", "devops", []),
    SeedSkill("GitHub Actions", "devops", []),
    SeedSkill("GitLab", "devops", []),
    SeedSkill("Linux", "os", []),
    SeedSkill("Bash", "os", ["shell scripting"]),
    # Methodology
    SeedSkill("Agile", "methodology", []),
    SeedSkill("Scrum", "methodology", []),
]

# (skill_a, skill_b, reason) — checked by stage 3's blocklist before any
# embedding-suggested match is accepted (docs/ARCHITECTURE.md §7).
INTERNAL_DISAMBIGUATION_PAIRS: list[tuple[str, str, str]] = [
    ("Java", "JavaScript", "Different languages despite the name; embeddings frequently conflate them."),
    ("React", "React Native", "Web framework vs. its separate mobile framework — related but not interchangeable."),
    (
        "Angular",
        "AngularJS",
        "Angular 2+ is a full rewrite of AngularJS (1.x); different frameworks, not versions of one.",
    ),
    ("PyTorch", "TensorFlow", "Competing ML frameworks; semantically adjacent enough for embeddings to conflate."),
    ("C++", "C#", "Share a name prefix and domain; syntactically and semantically distinct languages."),
]
