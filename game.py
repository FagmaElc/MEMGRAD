import random
import string
from collections import defaultdict



MEME_LIST_FILE = "data/memes.txt"
SITUATION_FILE = "data/situations.txt"


class GameSession:
    def __init__(self, chat_id, host_id):
        self.chat_id = chat_id
        self.host_id = host_id
        self.players = {}  # user_id: {user, memes, selected_meme}
        self.available_memes = self.load_memes()
        self.situations = self.load_situations()
        self.votes = defaultdict(set)  # meme_idx -> set(user_id), чтобы не было двойного голоса
        self.scores = defaultdict(int)  # user_id -> очки
        self.current_situation = None
        self.started = False

    def reset_votes(self):
        self.votes.clear()

    def load_memes(self):
        with open(MEME_LIST_FILE, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]

    def load_situations(self):
        with open(SITUATION_FILE, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]

    def add_player(self, user):
        if user.id in self.players:
            return False
        self.players[user.id] = {
            "user": user,
            "memes": [],
            "selected_meme": None
        }
        return True

    def deal_memes(self):
        for player in self.players.values():
            player["memes"] = random.sample(self.available_memes, 10)
            player["selected_meme"] = None  # Сброс выбора

    def pick_situation(self):
        self.current_situation = random.choice(self.situations)
        return self.current_situation

    def all_selected(self):
        return all(p["selected_meme"] is not None for p in self.players.values())

    def get_selected_memes(self):
        # Вернуть список URL выбранных мемов
        selected = []
        for p in self.players.values():
            idx = p["selected_meme"]
            if idx is not None and 0 <= idx < len(p["memes"]):
                selected.append(p["memes"][idx])
        return selected


class GameManager:
    def __init__(self):
        self.games = {}

    def generate_code(self):
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

    def create_game(self, chat_id, host_user):
        code = self.generate_code()
        game = GameSession(chat_id, host_user.id)
        game.add_player(host_user)  # Добавляем хоста в игроков
        self.games[code] = game
        return code


    def join_game(self, code, user):
        game = self.games.get(code)
        if not game:
            return False

        user_id = user.id
        if user_id in game.players:
            return False  # Уже в игре

        game.players[user_id] = {
            "user": user,
            "memes": [],
            "selected_meme": None,
            "meme_messages": []  # ← вот это добавляем!
        }

        return True


    def get_game_by_host(self, host_id):
        for game in self.games.values():
            if game.host_id == host_id:
                return game
        return None

    def get_game_by_player(self, user_id):
        for game in self.games.values():
            if user_id in game.players:
                return game
        return None
