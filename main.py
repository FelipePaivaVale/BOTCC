import datetime
import nextcord
from nextcord.ext import commands
from database import Database
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
        return 1.5
    
    if total_time == 0:
        return 2.0
    
    odd = total_apostado / total_time
    return max(1.1, round(odd, 2))

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
    user = ctx.author
    
    saldo_atual = sb.get_saldo(user_id)
    if saldo_atual is None:
        await ctx.send("Você não está registrado. Use !registrar primeiro.")
        return
    
    stats = sb.get_estatisticas_apostas(user_id)
    total_apostas = stats['total_apostas']
    vitorias = stats['apostas_vencedoras']
    porcentagem = (vitorias / total_apostas * 100) if total_apostas > 0 else 0
    
    embed = nextcord.Embed(
        title=f"💰 Perfil de {user.display_name}",
        color=0x00ff00
    )
    
    embed.set_thumbnail(url=user.display_avatar.url)
    
    embed.add_field(
        name="Saldo Atual",
        value=f"🪙 {saldo_atual} moedas",
        inline=True
    )
    
    embed.add_field(
        name="Total Apostado",
        value=f"🎰 {stats['total_apostado']} moedas",
        inline=True
    )
    
    barra_length = 10
    preenchido = round(porcentagem / 100 * barra_length)
    barra = "🟩" * preenchido + "⬛" * (barra_length - preenchido)
    
    embed.add_field(
        name="Desempenho",
        value=(
            f"📊 Apostas: {total_apostas}\n"
            f"✅ Vitórias: {vitorias}\n"
            f"📈 Acertos: {porcentagem:.1f}%\n"
            f"{barra}"
        ),
        inline=False
    )
    embed.set_footer(text=f"ID: {user_id} • Use !apostar para aumentar seu saldo!")
    await ctx.send(embed=embed)

@bot.command()
async def apostar(ctx, time: str, valor: int):
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
        name="!odds",
        value="Mostra as odds de todas as partidas ativas",
        inline=False
    )

    help_embed.add_field(
        name="!minhas_apostas",
        value="Mostra todas as suas apostas e seus status",
        inline=False
    )
    
    help_embed.add_field(
        name="!historico [limite]",
        value="Mostra o histórico de partidas finalizadas (padrão: 5)",
        inline=False
    )

    help_embed.add_field(
        name="!rank [limite]",
        value="Mostra o ranking dos usuários com maior saldo (padrão: 10, máximo: 20)",
        inline=False
    )
    
    await ctx.send(embed=help_embed)

@bot.command()
async def iniciar_partida(ctx, time1: str, time2: str):
    if ctx.author.guild_permissions.administrator:
        partidas_ativas = sb.get_partidas_ativas()
        for partida in partidas_ativas:
            if time1 in [partida['time1'], partida['time2']] or time2 in [partida['time1'], partida['time2']]:
                await ctx.send(f"Erro: Time '{time1}' ou '{time2}' já está em uma partida ativa!")
                return
        
        match_id = sb.registrar_partida(time1, time2)
        matches[match_id] = {
            'time1': time1,
            'time2': time2,
            'apostas': {time1: {}, time2: {}},
            'finalizado': False
        }

        embed = nextcord.Embed(
            title=" NOVA PARTIDA INICIADA! ",
            description=f"**Partida ID: {match_id}**",
            color=0x00ff00 
        )
        
        embed.add_field(
            name="Times",
            value=f"🏆 **{time1}** vs **{time2}**",
            inline=False
        )
        
        embed.add_field(
            name="Como apostar",
            value=f"Use `!apostar {match_id} [time] [valor]`",
            inline=False
        )
        
        embed.set_footer(
            text=f"Partida criada por {ctx.author.display_name}",
            icon_url=ctx.author.display_avatar.url
        )
        
        embed.timestamp = datetime.datetime.now()
        
        await ctx.send(embed=embed)
    else:
        embed = nextcord.Embed(
            title="❌ Acesso Negado",
            description="Você precisa ser administrador para iniciar partidas!",
            color=0xff0000
        )
        await ctx.send(embed=embed)

@bot.command()
async def finalizar_partida(ctx, match_id: int, vencedor: str):
    if ctx.author.guild_permissions.administrator:
        if match_id not in matches or matches[match_id]['finalizado']:
            await ctx.send("Partida não encontrada ou já finalizada!")
            return
        
        if vencedor not in matches[match_id]['apostas']:
            await ctx.send("Time vencedor inválido!")
            return
        
        sb.finalizar_partida(match_id, vencedor)
        matches[match_id]['finalizado'] = True
        matches[match_id]['vencedor'] = vencedor 
        
        apostas_vencedoras = sb.get_apostas_vencedoras(match_id, vencedor)
        
        for aposta in apostas_vencedoras:
            user_id = aposta['user_id']
            valor = aposta['valor']
            multiplicador = aposta['multiplicador']
            ganho = int(valor * multiplicador)
            sb.atualizar_saldo(user_id, sb.get_saldo(user_id) + ganho)
        
        await ctx.send(f"O time {vencedor} venceu a partida {match_id}! Pagamentos realizados.")
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

@bot.command()
async def minhas_apostas(ctx):
    user_id = ctx.author.id
    apostas = sb.get_minhas_apostas(user_id)
    
    if not apostas:
        await ctx.send("Você não fez nenhuma aposta ainda!")
        return
    
    embed = nextcord.Embed(
        title="Suas Apostas",
        color=0x3498db
    )
    
    for aposta in apostas:
        partida_info = aposta.get("partidas", {})
        finalizada = partida_info.get("finalizada", False)
        vencedor = partida_info.get("vencedor")
        
        if not finalizada:
            status = "🔄 Em andamento"
        elif aposta["time"] == vencedor:
            status = "✅ Ganha"
        else:
            status = "❌ Perdida"
        
        embed.add_field(
            name=f"Partida {aposta['match_id']}: {partida_info.get('time1', '?')} vs {partida_info.get('time2', '?')}",
            value=f"Time: {aposta['time']}\nValor: {aposta['valor']} moedas\nOdd: {aposta['multiplicador']}x\nStatus: {status}",
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.command()
async def historico(ctx, limit: int = 5):
    historico = sb.get_historico_partidas(limit)
    
    if not historico:
        await ctx.send("Nenhuma partida finalizada ainda!")
        return
    
    embed = nextcord.Embed(
        title=f"Últimas {len(historico)} partidas",
        color=0xe67e22
    )
    
    for partida in historico:
        embed.add_field(
            name=f"Partida {partida['id']}: {partida['time1']} vs {partida['time2']}",
            value=f"Vencedor: {partida['vencedor']}\nFinalizada em: {partida['created_at'][:10]}",
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.command()
async def rank(ctx, limit: int = 10):
    if limit > 20 or limit < 1:
        await ctx.send("Por favor, especifique um limite entre 1 e 20.")
        return

    ranking = sb.get_ranking(limit)
    
    if not ranking:
        await ctx.send("Nenhum usuário encontrado!")
        return
    
    embed = nextcord.Embed(
        title=f"🏆 Ranking Top {len(ranking)}",
        description="Usuários com maior saldo",
        color=0xffd700
    )
    
    medalhas = ["🥇", "🥈", "🥉"] + ["🔹"] * 7 
    
    for i, usuario in enumerate(ranking):
        nome = usuario['nome']
        saldo = usuario['saldo']
        posicao = i + 1
        
        if i < len(medalhas):
            prefixo = medalhas[i]
        else:
            prefixo = f"{posicao}."
        
        embed.add_field(
            name=f"{prefixo} {nome}",
            value=f"{saldo} moedas",
            inline=False
        )
    
    embed.set_footer(text=f"Seu saldo: {sb.get_saldo(ctx.author.id)} moedas | !saldo para ver detalhes")
    await ctx.send(embed=embed)

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

bot.run(TOKEN)