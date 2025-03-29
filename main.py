import nextcord
from nextcord.ext import commands
from database import Database
import asyncio
import os
from dotenv import load_dotenv

intents = nextcord.Intents.default()
intents.message_content = True
sb = Database()
bot = commands.Bot(command_prefix="!", intents=intents)

matches = {}

@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')

def calcular_odds_justas(total_time, total_oponente):
    """
    Calcula odds P2P justas (sem margem da casa).
    Retorna 2.0 quando equilibrado e proporcional quando não.
    """
    total_apostado = total_time + total_oponente
    
    if total_time == 0 and total_oponente == 0:
        return 1.8  # Valor inicial justo (50%-50%)
    
    if total_time == 0:
        return float('inf')  # Retorna infinito se não há apostas no time
    
    odd = total_apostado / total_time
    return max(1.01, round(odd, 2))  # Mínimo de 1.01x

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
    
    match_id = None
    for id, match in matches.items():
        if not match['finalizado']:
            match_id = id
            break
    
    if match_id not in matches or matches[match_id]['finalizado']:
        ativas = [str(id) for id, m in matches.items() if not m['finalizado']]
        if ativas:
            await ctx.send(f"Partida inválida! Partidas ativas: {', '.join(ativas)}")
        else:
            await ctx.send("Não há partidas ativas no momento!")
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
    
    total_time1 = sum(matches[match_id]['apostas'][matches[match_id]['time1']].values()) if matches[match_id]['apostas'][matches[match_id]['time1']] else 0
    total_time2 = sum(matches[match_id]['apostas'][matches[match_id]['time2']].values()) if matches[match_id]['apostas'][matches[match_id]['time2']] else 0

    odds_time1 = calcular_odds_justas(total_time1, total_time2)
    odds_time2 = calcular_odds_justas(total_time2, total_time1)
    multiplicador = odds_time1 if time == matches[match_id]['time1'] else odds_time2

    sb.atualizar_saldo(user_id, saldo_atual - valor)

    sb.registrar_aposta(user_id, match_id, time, valor, multiplicador)

    matches[match_id]['apostas'][time][user_id] = valor

    await ctx.send(f"Aposta de {valor} moedas registrada no {time}! Multiplicador: {round(multiplicador, 2)}x")

@bot.command()
async def comandos(ctx):
    help_embed = nextcord.Embed(
        title="Ajuda do Bot de Apostas",
        description="Lista de todos os comandos disponíveis",
        color=0x00ff00
    )
    
    help_embed.add_field(
        name="!registrar",
        value="Registra um novo usuário no sistema",
        inline=False
    )
    
    help_embed.add_field(
        name="!saldo",
        value="Mostra seu saldo atual",
        inline=False
    )
    
    help_embed.add_field(
        name="!apostar <time> <valor>",
        value="Aposta em um time na partida ativa",
        inline=False
    )
    
    help_embed.add_field(
        name="!apostar <ID_partida> <time> <valor>",
        value="Aposta em um time da partida especificada\nUse !odds para ver IDs das partidas",
        inline=False
    )
    
    help_embed.add_field(
        name="!odds",
        value="Mostra as odds de todas as partidas ativas",
        inline=False
    )
    
    help_embed.add_field(
        name="!finalizar_partida <vencedor>",
        value="(Admin) Finaliza a partida ativa e paga os vencedores",
        inline=False
    )
    
    await ctx.send(embed=help_embed)

@bot.command()
async def iniciar_partida(ctx, time1: str, time2: str):
    if ctx.author.guild_permissions.administrator:
        # Verificar se times já estão em partidas ativas
        for match in matches.values():
            if not match['finalizado']:
                if time1 in [match['time1'], match['time2']] or time2 in [match['time1'], match['time2']]:
                    await ctx.send(f"Erro: O time '{time1}' ou '{time2}' já está em uma partida ativa!")
                    return
        
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
async def odds(ctx):
    partidas_ativas = {id: m for id, m in matches.items() if not m['finalizado']}
    
    if not partidas_ativas:
        await ctx.send("Não há partidas ativas no momento!")
        return
    
    embed = nextcord.Embed(
        title="Odds das Partidas Ativas",
        color=0x00ff00
    )
    
    for match_id, match in partidas_ativas.items():
        total_time1 = sum(match['apostas'][match['time1']].values()) if match['apostas'][match['time1']] else 0
        total_time2 = sum(match['apostas'][match['time2']].values()) if match['apostas'][match['time2']] else 0
        
        odds_time1 = calcular_odds_justas(total_time1, total_time2)
        odds_time2 = calcular_odds_justas(total_time2, total_time1)
        
        embed.add_field(
            name=f"Partida {match_id}: {match['time1']} vs {match['time2']}",
            value=f"{match['time1']}: {odds_time1}x\n{match['time2']}: {odds_time2}x",
            inline=False
        )
    
    await ctx.send(embed=embed)

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

bot.run(TOKEN)