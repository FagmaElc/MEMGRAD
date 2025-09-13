from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from game import GameManager
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InputMediaPhoto
import asyncio
from datetime import datetime
from aiogram.types.message import Message as AioMessage
from aiogram.types import Chat



router = Router()
games = GameManager()

@router.message(Command("startgame"))
async def start_game(message: Message):
    chat_id = message.chat.id
    code = games.create_game(chat_id, message.from_user)
    await message.answer(f"🎮 Игра создана! Код комнаты: <code>{code}</code>\nИгроки, введите /join {code} чтобы присоединиться.")

@router.message(Command("join"))
async def join_game(message: Message):
    try:
        code = message.text.split()[1]
    except IndexError:
        await message.reply("Введите код комнаты. Пример: /join ABC123")
        return

    success = games.join_game(code, message.from_user)
    if success:
        game = games.games.get(code)
        host_id = game.host_id
        host_name = game.players[host_id]["user"].full_name



        player_list = "\n".join([
            ("👑 " if uid == host_id else "• ") + data["user"].full_name
            for uid, data in game.players.items()
        ])

        await message.answer(
            f"✅ Вы присоединились к игре!\n\n"
            f"<b>Хост:</b> {host_name}\n"
            f"<b>Игроки:</b>\n{player_list}"
        )
    else:
        await message.answer("❌ Комната не найдена или вы уже присоединились.")

# ✅ ЭТО ВАЖНО: добавь эту функцию в конце файла
def register_handlers(dp):
    dp.include_router(router)

@router.message(Command("deal"))
async def deal_memes(message: Message):
    game = games.get_game_by_host(message.from_user.id)
    if not game:
        await message.answer("❌ Вы не являетесь хостом активной игры.")
        return

    if game.started:
        await message.answer("⚠️ Мемы уже были разосланы!")
        return

    game.deal_memes()
    game.started = True

    # Отправляем ситуацию
    situation = game.pick_situation()
    if not situation:
        await message.answer("⚠️ Нет доступных ситуаций!")
        return
    await message.bot.send_message(game.chat_id, f"📢 Первая ситуация:\n\n<b>{situation}</b>")

    # Раздаём мемы
    for player_id, data in game.players.items():
        user = data["user"]
        memes = data["memes"]

        # Debug: сообщим, что мемы для пользователя готовы
        print(f"Отправка мемов {len(memes)} шт. игроку {user.full_name} ({user.id})")

        for idx, meme_url in enumerate(memes):
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(
                        text=f"Выбрать этот мем ({idx+1})",
                        callback_data=f"select_{idx}"
                    )]
                ]
            )
            try:
                await message.bot.send_photo(
                    chat_id=user.id,
                    photo=meme_url,
                    caption=f"Мем {idx+1}",
                    reply_markup=keyboard
                )
            except Exception as e:
                # Debug сообщение об ошибке
                print(f"Ошибка отправки мемов пользователю {user.full_name} ({user.id}): {e}")
                await message.answer(
                    f"⚠️ Не удалось отправить мем игроку {user.full_name}. "
                    f"Он должен сначала написать боту в ЛС."
                )
                # НЕ прерываем цикл, продолжаем отправлять остальным

    host_name = game.players[game.host_id]["user"].full_name
    player_list = "\n".join([
        ("🕹 " if uid == game.host_id else "• ") + data["user"].full_name
        for uid, data in game.players.items()
    ])
    await message.answer(
        f"📤 Мемы были разосланы игрокам!\n\n"
        f"<b>Хост:</b> {host_name}\n"
        f"<b>Игроки:</b>\n{player_list}"
    )

async def send_memes(game, bot):
    for player_id, data in game.players.items():
        user = data["user"]
        memes = data["memes"]

        # 🧹 Удаление старых сообщений в ЛС
        old_messages = data.get("meme_messages", [])
        for msg_id in old_messages:
            try:
                await bot.delete_message(chat_id=user.id, message_id=msg_id)
            except Exception as e:
                print(f"❌ Не удалось удалить сообщение {msg_id} у {user.full_name}: {e}")
        # Очищаем список после удаления
        data["meme_messages"] = []

        # 📤 Отправка новых мемов
        for idx, meme_url in enumerate(memes):
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[[ 
                    InlineKeyboardButton(
                        text=f"Выбрать мем {idx + 1}",
                        callback_data=f"select_{idx}"
                    )
                ]]
            )
            try:
                msg = await bot.send_photo(
                    chat_id=user.id,
                    photo=meme_url,
                    caption=f"Мем {idx + 1}",
                    reply_markup=keyboard
                )
                # ✅ Сохраняем ID сообщения, чтобы удалить позже
                data["meme_messages"].append(msg.message_id)
            except Exception as e:
                print(f"Ошибка отправки мемов {user.full_name} ({user.id}): {e}")
                await bot.send_message(
                    chat_id=game.chat_id,
                    text=f"⚠️ Не удалось отправить мем игроку {user.full_name}. "
                         f"Он должен сначала написать боту в ЛС."
                )


async def send_next_round(bot, game):
    # Проверка, есть ли хотя бы у одного игрока мемы
    players_with_memes = [
        player for player in game.players.values() if player["memes"]
    ]

    if not players_with_memes:
        await end_game(bot, game)
        return

    situation = game.pick_situation()
    await bot.send_message(game.chat_id, f"📢 Ситуация:\n\n<b>{situation}</b>")

    for player_id, data in game.players.items():
        user = data["user"]
        memes = data["memes"]

        for idx, meme_url in enumerate(memes):
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(
                        text=f"Выбрать мем {idx+1}",
                        callback_data=f"select_{idx}"
                    )]
                ]
            )
            try:
                await bot.send_photo(
                    chat_id=user.id,
                    photo=meme_url,
                    caption=f"Мем {idx+1}",
                    reply_markup=keyboard
                )
            except Exception:
                await bot.send_message(
                    game.chat_id,
                    f"⚠️ Не удалось отправить мем игроку {user.full_name}. "
                    f"Он должен сначала написать боту в ЛС."
                )


@router.message(Command("nextround"))
async def next_round(message: Message):
    game = games.get_game_by_host(getattr(message.from_user, "id", 0))
    if not game:
        await message.answer("❌ Вы не являетесь хостом активной игры.")
        return

    await send_next_round(message.bot, game)

        
@router.callback_query(lambda c: c.data and c.data.startswith("vote_"))
async def process_vote(callback: CallbackQuery):
    user_id = callback.from_user.id
    game = games.get_game_by_player(user_id)

    if not game:
        await callback.answer("❌ Вы не участвуете в игре.")
        return

    vote_idx = int(callback.data.split("_")[1])

    author_id = game.selected_for_vote[vote_idx][0]
    if user_id == author_id:
        await callback.answer("❌ Вы не можете голосовать за свой мем.")
        return

    # Удаляем предыдущие голоса пользователя
    for voters in game.votes.values():
        voters.discard(user_id)

    # Добавляем голос
    if vote_idx not in game.votes:
        game.votes[vote_idx] = set()
    game.votes[vote_idx].add(user_id)

    await callback.answer(f"Вы проголосовали за мем #{vote_idx + 1}.")

    # Кому нужно голосовать — все, кроме авторов мемов
    authors = {author_id for author_id, _ in game.selected_for_vote}
    voters_needed = set(game.players.keys()) - authors

    # Кто уже проголосовал
    voters_who_voted = set()
    for voters in game.votes.values():
        voters_who_voted.update(voters)

    print(f"Нужны голоса от: {voters_needed}")
    print(f"Уже проголосовали: {voters_who_voted}")

    # Проверка, что все проголосовали и никто не пропущен
    if voters_needed and voters_needed.issubset(voters_who_voted):
        # Все проголосовали
        await end_vote(callback.message, bot=callback.bot, game=game)

@router.callback_query(lambda c: c.data and c.data.startswith("select_"))
async def process_selection(callback: CallbackQuery):
    user_id = callback.from_user.id
    selected_idx = int(callback.data.split("_")[1])

    game = games.get_game_by_player(user_id)
    if not game:
        await callback.answer("❌ Вы не участвуете в игре.")
        return

    player_data = game.players.get(user_id)
    if player_data is None:
        await callback.answer("❌ Вы не участник этой игры.")
        return

    player_data["selected_meme"] = selected_idx
    await callback.answer(f"Вы выбрали мем #{selected_idx + 1}")

    if game.all_selected():
        selected_memes = []
        game.selected_for_vote = []
        game.reset_votes()
        game.voting_message_ids = []

        for player_id, player in game.players.items():
            idx = player["selected_meme"]
            if idx is not None and 0 <= idx < len(player["memes"]):
                meme_url = player["memes"][idx]
                selected_memes.append((player_id, meme_url))
                game.selected_for_vote.append((player_id, meme_url))
                del player["memes"][idx]
                player["selected_meme"] = None

        for i, (author_id, meme_url) in enumerate(selected_memes):
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"Голосовать за мем #{i+1}", callback_data=f"vote_{i}")]
            ])
            msg = await callback.bot.send_photo(
                chat_id=game.chat_id,
                photo=meme_url,
                reply_markup=keyboard,
                caption=f"Мем #{i+1} (автор: {game.players[author_id]['user'].full_name})"
            )
            game.voting_message_ids.append(msg.message_id)

        await callback.bot.send_message(game.chat_id, "🎉 Голосование началось! У вас 30 секунд, чтобы проголосовать.")

        # Запускаем таймер завершения голосования и следующий раунд
        async def vote_timer():
            await asyncio.sleep(30)
            # Подсчитываем результаты
            await end_vote(callback.message, bot=callback.bot, game=game)
            # Запускаем следующий раунд
            await next_round_auto(callback.bot, game)

        asyncio.create_task(vote_timer())

async def next_round_auto(bot, game):
        # Проверка, есть ли хотя бы у одного игрока мемы
    players_with_memes = [
        player for player in game.players.values() if player["memes"]
    ]

    if not players_with_memes:
        await end_game(bot, game)
        return

    situation = game.pick_situation()
    await bot.send_message(game.chat_id, f"📢 Следующая ситуация:\n\n<b>{situation}</b>")

    for player_id, data in game.players.items():
        user = data["user"]
        memes = data["memes"]

        for idx, meme_url in enumerate(memes):
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(
                        text=f"Выбрать мем {idx+1}",
                        callback_data=f"select_{idx}"
                    )]
                ]
            )
            try:
                await bot.send_photo(
                    chat_id=user.id,
                    photo=meme_url,
                    caption=f"Мем {idx+1}",
                    reply_markup=keyboard
                )
            except Exception:
                await bot.send_message(game.chat_id,
                    f"⚠️ Не удалось отправить мем игроку {user.full_name}. "
                    f"Он должен сначала написать боту в ЛС.")





async def end_vote(message: Message, bot=None, game=None):
    if bot is None:
        bot = message.bot

    if game is None:
        game = games.get_game_by_host(message.from_user.id)

    if not game:
        await bot.send_message(message.chat.id, "❌ Вы не являетесь хостом активной игры.")
        return

    if not game.selected_for_vote:
        await bot.send_message(message.chat.id, "⚠️ Голосование уже завершено или не началось.")
        return

    votes_count = {idx: len(voters) for idx, voters in game.votes.items()}
    if not votes_count:
        await bot.send_message(message.chat.id, "⚠️ Голосов нет.")
        return

    max_votes = max(votes_count.values())
    winners = [idx for idx, cnt in votes_count.items() if cnt == max_votes]

    for winner_idx in winners:
        author_id = game.selected_for_vote[winner_idx][0]
        game.scores[author_id] += 1

    result_text = "🏆 Результаты голосования:\n"
    for idx, (author_id, _) in enumerate(game.selected_for_vote):
        count = votes_count.get(idx, 0)
        name = game.players[author_id]["user"].full_name
        score = game.scores.get(author_id, 0)
        result_text += f"Мем #{idx+1} от {name}: {count} голосов, всего очков: {score}\n"

    await bot.send_message(game.chat_id, result_text)

    game.reset_votes()
    game.selected_for_vote = []

async def end_game(bot, game):
    await bot.send_message(game.chat_id, "🏁 Игра окончена! Подсчитываем очки...")

    # Подсчёт очков
    score_data = [(uid, score) for uid, score in game.scores.items()]
    score_data.sort(key=lambda x: x[1], reverse=True)

    if not score_data:
        await bot.send_message(game.chat_id, "😢 Никто не набрал очков.")
        return

    max_score = score_data[0][1]
    winners = [uid for uid, score in score_data if score == max_score]

    if len(winners) == 1:
        winner_name = game.players[winners[0]]["user"].full_name
        await bot.send_message(game.chat_id, f"🎉 Победитель: <b>{winner_name}</b> с {max_score} очками!")
    else:
        names = [game.players[uid]["user"].full_name for uid in winners]
        name_list = ", ".join(names)
        await bot.send_message(game.chat_id, f"🤝 Ничья между: <b>{name_list}</b>\nКаждый набрал {max_score} очков!")

    # Можно очистить игру из памяти (если нужно)
    del games.games[game.code]

