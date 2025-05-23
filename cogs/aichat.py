import io
import json
import os
import re
from typing import Dict, List, Union

import aiofiles
import discord
import discord.http
import dotenv
import httpx
from discord.ext import commands
from google import genai
from google.genai import chats, types
from PIL import Image
from pydantic import TypeAdapter

from datas import colours, imageUrl, messages, systemInstructs

dotenv.load_dotenv()

SAFETY_SETTINGS = [
    types.SafetySetting(
        category="HARM_CATEGORY_HATE_SPEECH",
        threshold="BLOCK_NONE",
    ),
    types.SafetySetting(
        category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
        threshold="BLOCK_NONE",
    ),
    types.SafetySetting(
        category="HARM_CATEGORY_DANGEROUS_CONTENT",
        threshold="BLOCK_NONE",
    ),
    types.SafetySetting(
        category="HARM_CATEGORY_HARASSMENT",
        threshold="BLOCK_NONE",
    ),
]


class AIChatCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.http = httpx.AsyncClient()
        self.genai = genai.Client(api_key=os.getenv("gemini"))
        self.chats: Dict[int, Dict[str, chats.AsyncChat]] = {}
        self.generating: Dict[int, bool] = {}
        self.histories: Dict[int, Dict[str, List[types.Content]]] = {}
        self.defaultCharacter: Dict[int, str] = {}

    async def cog_load(self):
        if not os.path.exists("chat.json"):
            async with aiofiles.open("chat.json", "w") as f:
                await f.write("{}")

        async with aiofiles.open("chat.json", "r") as f:
            raw = json.loads(await f.read())

        adapter = TypeAdapter(Dict[int, Dict[str, List[types.Content]]])
        self.histories: Dict[int, Dict[str, List[types.Content]]] = (
            adapter.validate_python(raw)
        )

        if not os.path.exists("default.json"):
            async with aiofiles.open("default.json", "w") as f:
                await f.write("{}")

        async with aiofiles.open("default.json", "r") as f:
            raw: Dict[str, str] = json.loads(await f.read())

        self.defaultCharacter: Dict[int, str] = {
            int(userId): character for userId, character in raw.items()
        }

    async def cog_unload(self):
        asDict = {
            userId: {
                character: [chat.model_dump() for chat in chats]
                for character, chats in characters.items()
            }
            for userId, characters in self.histories.items()
        }

        async with aiofiles.open("chat.json", "w") as f:
            await f.write(json.dumps(asDict))

        async with aiofiles.open("default.json", "w") as f:
            await f.write(json.dumps(self.defaultCharacter))

    @commands.command()
    async def characters(self, ctx: commands.Context):
        await ctx.reply(f"`{list(systemInstructs.keys())}`")

    @commands.command()
    async def default(self, ctx: commands.Context, character: str = None):
        if not character:
            for p in self.bot.command_prefix:
                if ctx.message.content.startswith(p):
                    prefix = p
                    break
            await ctx.reply(messages.DEFAULTHOWTO.format(prefix=prefix))
            return

        if character.isdigit():
            index = int(character)
            if index < len(systemInstructs.keys()):
                character = list(systemInstructs.keys())[index]
            else:
                await ctx.reply(
                    f"キャラクターのインデックスは`{len(systemInstructs.keys())-1}`まで受け付けています\n`{list(systemInstructs.keys())}`"
                )
                return

        if not character in systemInstructs:
            await ctx.reply(
                f"キャラクターは`{list(systemInstructs.keys())}`のいずれかでなければいけません"
            )
            return
        self.defaultCharacter[ctx.author.id] = character
        await ctx.reply(f"デフォルトのキャラクターを`{character}`にセットしました。")

    @commands.command()
    async def clear(self, ctx: commands.Context, character: str = None):
        if character:
            if character.isdigit():
                index = int(character)
                if index < len(systemInstructs.keys()):
                    character = list(systemInstructs.keys())[index]
                else:
                    await ctx.reply(
                        f"キャラクターのインデックスは`{len(systemInstructs.keys())-1}`まで受け付けています\n`{list(systemInstructs.keys())}`"
                    )
                    return

            if not character in systemInstructs:
                await ctx.reply(
                    f"キャラクターは`{list(systemInstructs.keys())}`のいずれかでなければいけません"
                )
                return

        if not ctx.author.id in self.chats:
            await ctx.reply("会話記録が保存されていません")
            return
        if not character:
            del self.chats[ctx.author.id]
            del self.histories[ctx.author.id]
            await ctx.reply("会話記録を削除しました。")
        else:
            if not character in self.chats[ctx.author.id]:
                await ctx.reply(f"`{character}`との会話記録が保存されていません")
                return
            del self.chats[ctx.author.id][character]
            del self.histories[ctx.author.id][character]
            await ctx.reply(f"`{character}`との会話記録を削除しました。")

    async def reply(
        self,
        message: Union[discord.Message, commands.Context],
        character: str,
        textContent: str,
    ):
        # もし12歳未満の年齢が入ったメッセージを送られてきた場合は、自動で通報
        if re.match(
            r"\b(０|１|２|３|４|５|６|７|８|９|0|1|2|3|4|5|6|7|8|9|10|11)\s*(歳|さい|yo|years old)\b",
            textContent,
        ):
            if isinstance(message, commands.Context):
                msg = message.message
            else:
                msg = message

            response = await self.bot.http.request(
                discord.http.Route("POST", "/reporting/message"),
                json={
                    "breadcrumbs": [7, 76, 86, 112],
                    "channel_id": str(msg.channel.id),
                    "elements": {},
                    "language": "en",
                    "message_id": str(msg.id),
                    "name": "message",
                    "variant": "6",
                    "version": "1.0",
                },
            )

            if "report_id" in response:
                await message.reply("メッセージを通報しました。もう遅い諦めろ")
                return
            else:
                print(response)

        if character.isdigit():
            index = int(character)
            if index < len(systemInstructs.keys()):
                character = list(systemInstructs.keys())[index]
            else:
                await message.reply(
                    f"キャラクターのインデックスは`{len(systemInstructs.keys())-1}`まで受け付けています\n`{list(systemInstructs.keys())}`"
                )
                return

        if not character in systemInstructs:
            await message.reply(
                f"キャラクターは`{list(systemInstructs.keys())}`のいずれかでなければいけません"
            )
            return

        if not message.author.id in self.chats:
            self.chats[message.author.id] = dict()
        if not character in self.chats[message.author.id]:
            self.chats[message.author.id][character] = self.genai.aio.chats.create(
                model="gemini-2.0-flash",
                config=types.GenerateContentConfig(
                    system_instruction=systemInstructs[character],
                    safety_settings=SAFETY_SETTINGS,
                ),
                history=self.histories.get(message.author.id, {}).get(character, []),
            )

        chat = self.chats[message.author.id][character]

        if not message.author.id in self.generating:
            self.generating[message.author.id] = True
        elif self.generating[message.author.id]:
            return

        try:
            async with message.channel.typing():
                messages = [textContent]

                if isinstance(message, commands.Context):
                    msg = message.message
                else:
                    msg = message

                for file in msg.attachments:
                    messages.append(Image.open(io.BytesIO(await file.read())))

                content = await chat.send_message(messages)

                chunkSize = 85
                chunks = [
                    content.text[i : i + chunkSize]
                    for i in range(0, len(content.text), chunkSize)
                ]

                linkStrings: List[str] = []

                omg = [f"[⁠︎](https://{character}.local/)"]

                for i, text in enumerate(chunks):
                    response = await self.http.post(
                        "https://nemtudo.me/api/tools/embeds",
                        json={
                            "title": character if i == 0 else "",
                            "description": text,
                            "image": imageUrl[character] if i == 0 else "",
                            "thumbImage": True,
                            "color": colours[character],
                        },
                    )
                    jsonData = response.json()
                    if jsonData["status"] != 200 or response.status_code != 200:
                        await message.reply("生成に失敗しました")
                        return

                    linkStrings.append(
                        f"[⁠︎](https://nemtudo.me/e/{jsonData['data']['id']})"
                    )

                chunkSize = 4
                chunks = [
                    linkStrings[i : i + chunkSize]
                    for i in range(0, len(linkStrings), chunkSize)
                ]
                for chunk in chunks:
                    try:
                        await message.reply(" ".join(omg + chunk))
                    except:
                        await message.reply(" ".join([omg[0] + chunk[0]]))
        finally:
            self.generating[message.author.id] = False
            if message.author.id not in self.histories:
                self.histories[message.author.id] = {}
            self.histories[message.author.id][character] = chat.get_history()

    # メッセージにリプライしたとき
    @commands.Cog.listener("on_message")
    async def onMessage(self, message: discord.Message):
        if not message.reference:
            return

        if not message.reference.resolved:
            try:
                resolved: discord.Message = await message.channel.fetch_message(
                    message.reference.message_id
                )
            except:
                pass
                return
        else:
            resolved: discord.Message = message.reference.resolved

        if resolved.author.id != self.bot.user.id:
            return
        for prefix in self.bot.command_prefix:
            if message.clean_content.startswith(prefix):
                return
        if message.author.bot:
            return

        character = resolved.clean_content.split("/")[2].split(".")[0]
        await self.reply(message, character, message.clean_content)

    # メンションしたとき
    @commands.Cog.listener("on_message")
    async def onMention(self, message: discord.Message):
        if message.author.bot:
            return
        if message.reference:
            return
        if not message.guild.me in message.mentions:
            return

        character = str(self.defaultCharacter.get(message.author.id, 0))
        await self.reply(
            message, character, message.clean_content.replace("@あいちゃ", "")
        )

    # コマンドを実行したとき
    @commands.command(alias="c")
    async def chat(
        self, ctx: commands.Context, character: str = None, *, text: str = None
    ):
        if not character or not text:
            for p in self.bot.command_prefix:
                if ctx.message.content.startswith(p):
                    prefix = p
                    break

            await ctx.reply(messages.CHATHOWTO.format(prefix=prefix))
            return

        await self.reply(ctx, character, text)


async def setup(bot: commands.Bot):
    await bot.add_cog(AIChatCog(bot))
