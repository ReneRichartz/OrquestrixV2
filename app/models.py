from datetime import datetime
from enum import Enum
from .extensions import db


class UserRole(Enum):
    BASIC = "basic"
    ADVANCED = "advanced"
    FULL = "full"
    ADMIN = "admin"




class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class User(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=True)
    role = db.Column(db.String(32), default=UserRole.ADMIN.value, nullable=False)  # V1 alle admin

    chats = db.relationship("Chat", back_populates="user", lazy="dynamic")
    projects = db.relationship("Project", back_populates="user", lazy="dynamic")
    workers = db.relationship("Worker", back_populates="user", lazy="dynamic")


class VectorStore(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    openai_vector_store_id = db.Column(db.String(100), unique=True, nullable=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<VectorStore {self.name}>"


chat_vector_store = db.Table(
    "chat_vector_store",
    db.Column("chat_id", db.Integer, db.ForeignKey("chat.id"), primary_key=True),
    db.Column("vector_store_id", db.Integer, db.ForeignKey("vector_store.id"), primary_key=True),
)

project_vector_store = db.Table(
    "project_vector_store",
    db.Column("project_id", db.Integer, db.ForeignKey("project.id"), primary_key=True),
    db.Column("vector_store_id", db.Integer, db.ForeignKey("vector_store.id"), primary_key=True),
)

worker_vector_store = db.Table(
    "worker_vector_store",
    db.Column("worker_id", db.Integer, db.ForeignKey("worker.id"), primary_key=True),
    db.Column("vector_store_id", db.Integer, db.ForeignKey("vector_store.id"), primary_key=True),
)


class File(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    openai_file_id = db.Column(db.String(100), unique=True, nullable=True)
    filename = db.Column(db.String(255), nullable=False)
    purpose = db.Column(db.String(50), default="assistants", nullable=False)
    size_bytes = db.Column(db.Integer, nullable=True)
    # Cache ob Datei irgendeinem Vector Store zugeordnet ist (Performance / Filter)
    in_vector_store = db.Column(db.Boolean, default=False, nullable=False)
    # JSON (Text) Liste der zugeordneten VectorStore OpenAI IDs (Cache)
    vector_store_ids_cache = db.Column(db.Text, nullable=True)

    # Beziehungen zu VectorStores (Dateien, die in einen Vector Store eingebettet wurden)
    vector_stores = db.relationship("VectorStore", secondary=lambda: vector_store_file, back_populates="files")

    def __repr__(self):
        return f"<File {self.filename}>"


chat_file = db.Table(
    "chat_file",
    db.Column("chat_id", db.Integer, db.ForeignKey("chat.id"), primary_key=True),
    db.Column("file_id", db.Integer, db.ForeignKey("file.id"), primary_key=True),
)

project_file = db.Table(
    "project_file",
    db.Column("project_id", db.Integer, db.ForeignKey("project.id"), primary_key=True),
    db.Column("file_id", db.Integer, db.ForeignKey("file.id"), primary_key=True),
)

worker_file = db.Table(
    "worker_file",
    db.Column("worker_id", db.Integer, db.ForeignKey("worker.id"), primary_key=True),
    db.Column("file_id", db.Integer, db.ForeignKey("file.id"), primary_key=True),
)


class Assistant(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    openai_assistant_id = db.Column(db.String(100), unique=True, nullable=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    model = db.Column(db.String(100), nullable=False)
    instructions = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<Assistant {self.name}>"


class Project(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    user = db.relationship("User", back_populates="projects")
    chats = db.relationship("Chat", back_populates="project", lazy="dynamic")
    workers = db.relationship("Worker", back_populates="project", lazy="dynamic")

    vector_stores = db.relationship("VectorStore", secondary=project_vector_store, backref="projects")
    files = db.relationship("File", secondary=project_file, backref="projects")

    def __repr__(self):
        return f"<Project {self.name}>"


class Chat(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    objective = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    max_output_tokens = db.Column(db.Integer, default=1024)
    model = db.Column(db.String(100), default="gpt-4.5")
    chat_role_id = db.Column(db.Integer, db.ForeignKey("chat_role.id"), nullable=True)

    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=True)

    user = db.relationship("User", back_populates="chats")
    messages = db.relationship("Message", back_populates="chat", cascade="all, delete-orphan", lazy="dynamic")
    project = db.relationship("Project", back_populates="chats")

    vector_stores = db.relationship("VectorStore", secondary=chat_vector_store, backref="chats")
    files = db.relationship("File", secondary=chat_file, backref="chats")

    def __repr__(self):
        return f"<Chat {self.title}>"


class ChatRole(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    instructions = db.Column(db.Text, nullable=False)
    model = db.Column(db.String(100), nullable=False, default="gpt-4.5")
    active = db.Column(db.Boolean, default=True)
    temperature = db.Column(db.Float, nullable=False, default=0.7)

    chats = db.relationship("Chat", backref="chat_role", lazy="dynamic")

    def __repr__(self):
        return f"<ChatRole {self.name}>"


class Message(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.Integer, db.ForeignKey("chat.id"), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # user / assistant / system
    content = db.Column(db.Text, nullable=False)
    openai_response_id = db.Column(db.String(100), nullable=True)

    chat = db.relationship("Chat", back_populates="messages")

    def __repr__(self):
        return f"<Message {self.role} {self.id}>"


class Worker(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    assistant_id = db.Column(db.Integer, db.ForeignKey("assistant.id"), nullable=True)
    openai_thread_id = db.Column(db.String(100), nullable=True)
    model = db.Column(db.String(100), default="gpt-4.1")

    user = db.relationship("User", back_populates="workers")
    project = db.relationship("Project", back_populates="workers")
    assistant = db.relationship("Assistant")

    vector_stores = db.relationship("VectorStore", secondary=worker_vector_store, backref="workers")
    files = db.relationship("File", secondary=worker_file, backref="workers")

    def __repr__(self):
        return f"<Worker {self.name}>"


class WorkerLog(db.Model, TimestampMixin):
    __tablename__ = 'worker_log'
    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey('worker.id'), nullable=False)
    input_text = db.Column(db.Text, nullable=False)
    output_text = db.Column(db.Text, nullable=True)
    openai_run_id = db.Column(db.String(100), nullable=True)
    run_status = db.Column(db.String(50), nullable=True)
    output_file_ids = db.Column(db.Text, nullable=True)  # JSON Liste von File IDs

    worker = db.relationship('Worker', backref=db.backref('logs', lazy='dynamic', cascade="all, delete-orphan"))

    def __repr__(self):
        return f"<WorkerLog {self.worker_id} {self.id}>"


# Association Table für VectorStore <-> File (Einbettungen)
vector_store_file = db.Table(
    "vector_store_file",
    db.Column("vector_store_id", db.Integer, db.ForeignKey("vector_store.id"), primary_key=True),
    db.Column("file_id", db.Integer, db.ForeignKey("file.id"), primary_key=True),
)

# Rückseitige Beziehung hinzufügen (nach Definition der Tabelle, um Referenz zu ermöglichen)
VectorStore.files = db.relationship("File", secondary=vector_store_file, back_populates="vector_stores")
