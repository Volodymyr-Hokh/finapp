from .users import UserRepository
from .accounts import AccountRepository
from .categories import CategoryRepository
from .tags import TagRepository
from .transactions import TransactionRepository
from .budgets import BudgetRepository
from .ai_logs import AILogRepository
from .chats import ChatRepository
from .chat_messages import ChatMessageRepository


class RepositoryContainer:
    def __init__(self):
        self.users = UserRepository()
        self.accounts = AccountRepository()
        self.categories = CategoryRepository()
        self.tags = TagRepository()
        self.transactions = TransactionRepository()
        self.budgets = BudgetRepository()
        self.ai_logs = AILogRepository()
        self.chats = ChatRepository()
        self.chat_messages = ChatMessageRepository()