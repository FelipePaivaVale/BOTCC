import nextcord
from nextcord.ext import commands
import asyncio
import os
from dotenv import load_dotenv

class OddsConverter:
    @staticmethod
    def decimal_to_fractional(decimal_odds):
        numerator = round((decimal_odds - 1) * 100)
        denominator = 100
        return f"{numerator}/{denominator}"

    @staticmethod
    def decimal_to_american(decimal_odds):
        if decimal_odds >= 2:
            return f"+{round((decimal_odds - 1) * 100)}"
        else:
            return f"-{round(100 / (decimal_odds - 1))}"

    @staticmethod
    def american_to_decimal(american_odds):
        if american_odds > 0:
            return round(1 + (american_odds / 100), 2)
        else:
            return round(1 + (100 / abs(american_odds)), 2)

    @staticmethod
    def implied_probability(decimal_odds):
        return round(1 / decimal_odds * 100, 2)

    @staticmethod
    def adjust_odds_for_margin(odds_list):
        probabilities = [1 / odd for odd in odds_list]
        total_prob = sum(probabilities)
        adjusted_odds = [round(1 / (prob / total_prob), 2) for prob in probabilities]
        return adjusted_odds

intents = nextcord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=">>", intents=intents)

balances = {}
bets = {}
matches = {}

@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')

@bot.command()
async def saldo(ctx):
    user = ctx.author.id
    saldo = balances.get(user, 1000)
    await ctx.send(f"Seu saldo atual: {saldo} moedas")

@bot.command()
async def iniciar_partida(ctx, time1: str, time2: str):
    if ctx.author.guild_permissions.administrator:
        match_id = len(matches) + 1
        matches[match_id] = {
            'time1': time1,
            'time2': time2,
            'apostas': {time1: {}, time2: {}},
            'finalizado': False
        }
        await ctx.send(f"Partida {match_id} iniciada! Times: {time1} vs {time2}")
    else:
        await ctx.send("Você não tem permissão para iniciar partidas.")

@bot.command()
async def apostar(ctx, match_id: int, time: str, valor: int):
    user = ctx.author.id
    if user not in balances:
        balances[user] = 1000
    if balances[user] < valor:
        await ctx.send("Saldo insuficiente!")
        return
    
    if match_id not in matches or matches[match_id]['finalizado']:
        await ctx.send("Partida não encontrada ou já finalizada!")
        return
    
    if time not in matches[match_id]['apostas']:
        await ctx.send("Time inválido para esta partida!")
        return
    
    balances[user] -= valor
    matches[match_id]['apostas'][time][user] = matches[match_id]['apostas'][time].get(user, 0) + valor
    await ctx.send(f"Aposta de {valor} moedas registrada no {time}!")

@bot.command()
async def finalizar_partida(ctx, match_id: int, vencedor: str):
    if ctx.author.guild_permissions.administrator:
        if match_id not in matches or matches[match_id]['finalizado']:
            await ctx.send("Partida não encontrada ou já finalizada!")
            return
        
        if vencedor not in matches[match_id]['apostas']:
            await ctx.send("Time vencedor inválido!")
            return
        
        total_apostado = sum(sum(usuarios.values()) for usuarios in matches[match_id]['apostas'].values())
        total_vencedor = sum(matches[match_id]['apostas'][vencedor].values())
        odds = total_apostado / total_vencedor if total_vencedor > 0 else 1
        
        for user, valor in matches[match_id]['apostas'][vencedor].items():
            ganho = int(valor * odds)
            balances[user] = balances.get(user, 0) + ganho
        
        matches[match_id]['finalizado'] = True
        await ctx.send(f"O time {vencedor} venceu! Pagamentos realizados com odds de {round(odds, 2)}")
    else:
        await ctx.send("Você não tem permissão para finalizar partidas.")

@bot.command()
async def odds(ctx, match_id: int):
    if match_id not in matches or matches[match_id]['finalizado']:
        await ctx.send("Partida não encontrada ou já finalizada!")
        return
    
    total_apostado = sum(sum(usuarios.values()) for usuarios in matches[match_id]['apostas'].values())
    odds_time1 = total_apostado / sum(matches[match_id]['apostas'][matches[match_id]['time1']].values()) if sum(matches[match_id]['apostas'][matches[match_id]['time1']].values()) > 0 else 1
    odds_time2 = total_apostado / sum(matches[match_id]['apostas'][matches[match_id]['time2']].values()) if sum(matches[match_id]['apostas'][matches[match_id]['time2']].values()) > 0 else 1
    
    await ctx.send(f"Odds para a partida {match_id}:\n{matches[match_id]['time1']}: {round(odds_time1, 2)}\n{matches[match_id]['time2']}: {round(odds_time2, 2)}")

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

bot.run(TOKEN)