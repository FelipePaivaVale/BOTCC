import nextcord
from nextcord.ext import commands
from database import Database
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
sb = Database()
bot = commands.Bot(command_prefix="!", intents=intents)

matches = {}

@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')

@bot.command()
async def registrar(ctx):
    user_id = ctx.author.id
    user_name = ctx.author.name
    if sb.usuario_existe(user_id):
        await ctx.send("Você já está registrado!")
        return
    
    sb.registrar_usuario(user_id, user_name)
    await ctx.send(f"{user_name}, você foi registrado e recebeu 5000 moedas!")

@bot.command()
async def saldo(ctx):
    user_id = ctx.author.id
    saldo = sb.get_saldo(user_id)
    if saldo is None:
        await ctx.send("Você não está registrado. Use !registrar primeiro.")
        return
    
    await ctx.send(f"Seu saldo atual: {saldo} moedas")

@bot.command()
async def apostar(ctx, match_id: int, time: str, valor: int):
    user_id = ctx.author.id

    if match_id not in matches or matches[match_id]['finalizado']:
        await ctx.send("Partida não encontrada ou já finalizada!")
        return

    if time not in [matches[match_id]['time1'], matches[match_id]['time2']]:
        await ctx.send("Time inválido! Escolha entre os times da partida.")
        return

    if not sb.usuario_existe(user_id):
        await ctx.send("Você não está registrado. Use !registrar primeiro.")
        return

    saldo_atual = sb.get_saldo(user_id)
    if saldo_atual < valor:
        await ctx.send("Saldo insuficiente!")
        return

    total_apostado = sum(sum(apostas.values()) for apostas in matches[match_id]['apostas'].values())
    total_time1 = sum(matches[match_id]['apostas'][matches[match_id]['time1']].values()) if matches[match_id]['apostas'][matches[match_id]['time1']] else 0
    total_time2 = sum(matches[match_id]['apostas'][matches[match_id]['time2']].values()) if matches[match_id]['apostas'][matches[match_id]['time2']] else 0

    odds_time1 = (total_apostado / total_time1) if total_time1 > 0 else 1
    odds_time2 = (total_apostado / total_time2) if total_time2 > 0 else 1
    multiplicador = odds_time1 if time == matches[match_id]['time1'] else odds_time2

    sb.atualizar_saldo(user_id, saldo_atual - valor)

    sb.registrar_aposta(user_id, match_id, time, valor, multiplicador)

    matches[match_id]['apostas'][time][user_id] = valor

    await ctx.send(f"Aposta de {valor} moedas registrada no {time}! Multiplicador: {round(multiplicador, 2)}x")

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
async def finalizar_partida(ctx, match_id: int, vencedor: str):
    if ctx.author.guild_permissions.administrator:
        if match_id not in matches or matches[match_id]['finalizado']:
            await ctx.send("Partida não encontrada ou já finalizada!")
            return

        if vencedor not in matches[match_id]['apostas']:
            await ctx.send("Time vencedor inválido!")
            return

        apostas_vencedoras = sb.get_apostas_vencedoras(match_id, vencedor)

        for aposta in apostas_vencedoras:
            user_id = aposta['user_id']
            valor = aposta['valor']
            multiplicador = aposta['multiplicador']
            ganho = int(valor * multiplicador)

            sb.atualizar_saldo(user_id, sb.get_saldo(user_id) + ganho)

        matches[match_id]['finalizado'] = True
        sb.remover_apostas(match_id)

        await ctx.send(f"O time {vencedor} venceu! Pagamentos realizados.")
    else:
        await ctx.send("Você não tem permissão para finalizar partidas.")

@bot.command()
async def odds(ctx, match_id: int):
    if match_id not in matches or matches[match_id]['finalizado']:
        await ctx.send("Partida não encontrada ou já finalizada!")
        return

    match = matches[match_id]
    total_apostado = sum(sum(apostas.values()) for apostas in match['apostas'].values())
    total_time1 = sum(match['apostas'][match['time1']].values()) if match['apostas'][match['time1']] else 0
    total_time2 = sum(match['apostas'][match['time2']].values()) if match['apostas'][match['time2']] else 0

    odds_time1 = (total_apostado / total_time1) if total_time1 > 0 else 1
    odds_time2 = (total_apostado / total_time2) if total_time2 > 0 else 1

    await ctx.send(f"Odds para a partida {match_id}:\n"
                   f"{match['time1']}: {round(odds_time1, 2)}\n"
                   f"{match['time2']}: {round(odds_time2, 2)}")

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

bot.run(TOKEN)