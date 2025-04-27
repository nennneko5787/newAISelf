import io
import os
import re
from typing import Dict, List, Union

import discord
import discord.http
import dotenv
import httpx
from discord.ext import commands
from google import genai
from google.genai import chats, types
from PIL import Image

from datas import systemInstructs, imageUrl, colours

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

invisible = "||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​|| _ _ _ _ _ _ "


class AIChatCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.http = httpx.AsyncClient()
        self.genai = genai.Client(api_key=os.getenv("gemini"))
        self.chats: Dict[int, Dict[str, chats.AsyncChat]] = {}
        self.generating: Dict[int, bool] = {}

    @commands.command()
    async def characters(self, ctx: commands.Context):
        await ctx.reply(f"`{list(systemInstructs.keys())}`")

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
            await ctx.reply("会話記録を削除しました。")
        else:
            if not character in self.chats[ctx.author.id]:
                await ctx.reply(f"`{character}`との会話記録が保存されていません")
                return
            del self.chats[ctx.author.id][character]
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

                chunkSize = 100
                chunks = [
                    content.text[i : i + chunkSize]
                    for i in range(0, len(content.text), chunkSize)
                ]

                linkStrings: List[str] = []

                for text in chunks:
                    response = await self.http.post(
                        "https://nemtudo.me/api/tools/embeds",
                        json={
                            "title": character,
                            "description": text,
                            "image": imageUrl[character],
                            "thumbImage": True,
                            "color": colours[character],
                        },
                    )
                    jsonData = response.json()
                    if jsonData["status"] != 200 or response.status_code != 200:
                        await message.reply("生成に失敗しました")
                        return

                    linkStrings.append(f"https://nemtudo.me/e/{jsonData['data']['id']}")

                try:
                    await message.reply(
                        invisible + f"{character}," + " ".join(linkStrings)
                    )
                except:
                    await message.reply(invisible + f"{character}," + linkStrings[0])
        finally:
            self.generating[message.author.id] = False

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

        character = resolved.clean_content.replace(invisible, "").split(",")[0]
        await self.reply(message, character, message.clean_content)

    @commands.command()
    async def chat(self, ctx: commands.Context, character: str, *, text):
        await self.reply(ctx, character, text)


async def setup(bot: commands.Bot):
    await bot.add_cog(AIChatCog(bot))
