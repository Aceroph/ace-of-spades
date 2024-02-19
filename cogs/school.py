from utils import checks, subclasses, misc
from discord.ext import commands
from main import AceBot
import datetime
import pathlib
import discord
import json

schooldata = json.load(open(pathlib.Path(__file__).parent.parent / 'utils' / "schoolday.json", "r"))

class School(subclasses.Cog):
    def __init__(self, bot: AceBot):
        super().__init__()
        self.emoji = '\N{SCHOOL}'
        self.bot = bot

        self.start = datetime.datetime.strptime(schooldata["start"], "%Y-%m-%d")
        self.stop = datetime.datetime.strptime(schooldata["stop"], "%Y-%m-%d")
        self.schedule = schooldata["schedule"]
        self.classes = schooldata["classes"]
        self.hours = schooldata["hours"]
        self.noschool = [datetime.datetime.strptime(x, "%Y-%m-%d").date() for x in schooldata["no-school"]]
        

    def get_schoolday(self, day: datetime.datetime):
        delta = day - self.start
        
        schoolday = 0
        for i in range(delta.days + 1):
            x = self.start + datetime.timedelta(days=i)
            schoolday += 1 if x.weekday() < 5 and x.date() not in self.noschool else 0

        # error handler
        if day.weekday() in [5, 6] or day < self.start or day > self.stop:
            return 0

        return schoolday % 9 if schoolday % 9 != 0 else 9

    @checks.guild_command(971165718844440647)
    @commands.command()
    async def schedule(self, ctx: commands.Context, date: misc.Time=datetime.datetime.today()):
        """Prints today's or another day's schedule"""
        day = self.get_schoolday(date)
        schedule = self.schedule[day - 1]

        # errors
        if date < self.start or date > self.stop or date.date() in self.noschool or date.weekday() in [5, 6]:
            return await ctx.reply(f":warning: You don't even have school on {date.strftime('%Y-%m-%d')}")
        
        # embed
        embed = discord.Embed(color=discord.Color.green(), title="School Schedule", description=f"{date.date()} (Day {day})")
        for i, subject in enumerate(schedule):
            for x in self.classes:
                if x["code"] == subject:
                    data = x
                    break

            teacher = data["teacher"]

            embed.add_field(name=f"{data['descriptionShort']} - {subject}", value=f":teacher: {teacher['firstName']} {teacher['lastName']}\n\N{BUSTS IN SILHOUETTE} Group {data['group']}\n\N{CLOCK FACE TEN-THIRTY} {self.hours[i]}\n", inline=False)
        await ctx.reply(embed=embed)



async def setup(bot: AceBot):
    await bot.add_cog(School(bot))