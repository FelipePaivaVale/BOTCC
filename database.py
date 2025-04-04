import datetime
import supabase
from config import SUPABASE_URL, SUPABASE_KEY

class Database:
    def __init__(self):
        self.sb = supabase.create_client(SUPABASE_URL, SUPABASE_KEY)

    def usuario_existe(self, user_id):
        """Verifica se o usuário já está registrado."""
        user = self.sb.table("usuarios").select("id").eq("id", user_id).execute()
        return bool(user.data)

    def registrar_usuario(self, user_id, user_name):
        """Registra um novo usuário com 5000 moedas iniciais."""
        self.sb.table("usuarios").insert({"id": user_id, "nome": user_name, "saldo": 5000}).execute()

    def get_saldo(self, user_id):
        """Obtém o saldo do usuário."""
        user = self.sb.table("usuarios").select("saldo").eq("id", user_id).execute()
        return user.data[0]["saldo"] if user.data else None

    def apostar(self, user_id, time, valor):
        """Registra uma aposta e atualiza o saldo do usuário."""
        user = self.sb.table("usuarios").select("saldo").eq("id", user_id).execute()
        if not user.data or user.data[0]["saldo"] < valor:
            return False 

        self.sb.table("usuarios").update({"saldo": user.data[0]["saldo"] - valor}).eq("id", user_id).execute()
        self.sb.table("apostas").insert({"user_id": user_id, "time": time, "valor": valor}).execute()
        return True

    def calcular_resultado(self, vencedor):
        apostas = self.sb.table("apostas").select("user_id, valor").eq("time", vencedor).execute()

        if not apostas.data:
            return 1, []

        total_apostado = self.sb.table("apostas").select("valor").execute()
        total_vencedor = sum(aposta["valor"] for aposta in apostas.data)
        odds = sum(aposta["valor"] for aposta in total_apostado.data) / total_vencedor if total_vencedor > 0 else 1

        vencedores = []
        for aposta in apostas.data:
            ganho = int(aposta["valor"] * odds)
            self.sb.table("usuarios").update({"saldo": supabase.functions.increment(ganho)}).eq("id", aposta["user_id"]).execute()
            vencedores.append(aposta["user_id"])

        self.sb.table("apostas").delete().execute()
        return odds, vencedores
    
    def atualizar_saldo(self, user_id, novo_saldo):
        """Atualiza o saldo do usuário."""
        self.sb.table("usuarios").update({"saldo": novo_saldo}).eq("id", user_id).execute()

    def registrar_aposta(self, user_id, match_id, time, valor, multiplicador):
        """Registra uma aposta."""
        self.sb.table("apostas").insert({
            "user_id": user_id,
            "match_id": match_id,
            "time": time,
            "valor": valor,
            "multiplicador": multiplicador
        }).execute()

    def get_apostas_vencedoras(self, match_id, time):
        """Obtém todas as apostas vencedoras de uma partida."""
        apostas = self.sb.table("apostas").select("*").eq("match_id", match_id).eq("time", time).execute()
        return apostas.data

    def remover_apostas(self, match_id):
        """Remove todas as apostas de uma partida."""
        self.sb.table("apostas").delete().eq("match_id", match_id).execute()

    def registrar_partida(self, time1: str, time2: str):
        """Registra uma nova partida no banco de dados"""
        partida = self.sb.table("partidas").insert({
            "time1": time1,
            "time2": time2,
            "finalizada": False,
            "vencedor": None
        }).execute()
        return partida.data[0]["id"]

    def finalizar_partida(self, match_id: int, vencedor: str):
        """Marca uma partida como finalizada"""
        self.sb.table("partidas").update({
            "finalizada": True,
            "vencedor": vencedor
        }).eq("id", match_id).execute()

    def get_partidas_ativas(self):
        """Retorna todas as partidas não finalizadas"""
        return self.sb.table("partidas").select("*").eq("finalizada", False).execute().data

    def get_historico_partidas(self, limit=10):
        """Retorna o histórico de partidas finalizadas"""
        return self.sb.table("partidas").select("*").eq("finalizada", True).order("id", desc=True).limit(limit).execute().data

    def get_minhas_apostas(self, user_id: int):
        """Retorna todas as apostas de um usuário com status correto"""
        return self.sb.table("apostas").select( "*, partidas(time1, time2, finalizada, vencedor)").eq("user_id", user_id).execute().data
    
    def get_ranking(self, limit=10):
        """Retorna os usuários com maior saldo"""
        return self.sb.table("usuarios").select("id, nome, saldo").order("saldo", desc=True).limit(limit).execute().data
    
    def get_estatisticas_apostas(self, user_id: int):
        """Versão simplificada que evita o erro"""
        # 1. Total de apostas (não muda)
        total_apostas = self.sb.table("apostas").select("id", count="exact").eq("user_id", user_id).execute().count
        
        # 2. Valor total apostado (não muda)
        valor_apostado = self.sb.table("apostas").select("valor").eq("user_id", user_id).execute()
        total_apostado = sum(aposta['valor'] for aposta in valor_apostado.data) if valor_apostado.data else 0
        
        # 3. Apostas vencedoras (nova consulta segura)
        apostas = self.sb.table("apostas").select("match_id, time").eq("user_id", user_id).execute().data
        vitorias = 0
        
        for aposta in apostas:
            partida = self.sb.table("partidas").select("vencedor, finalizada").eq("id", aposta["match_id"]).execute().data
            if partida and partida[0]["finalizada"] and partida[0]["vencedor"] == aposta["time"]:
                vitorias += 1
        
        return {
            'total_apostas': total_apostas,
            'apostas_vencedoras': vitorias,
            'total_apostado': total_apostado
        }
    
    def registrar_resgate_diario(self, user_id: int):
        """Registra o resgate diário e atualiza o saldo"""
        try:
            # Verifica se já existe registro
            resgate = self.sb.table("resgates").select("*").eq("user_id", user_id).execute()
            
            if resgate.data:
                # Atualiza registro existente
                self.sb.table("resgates").update({
                    "ultimo_resgate": datetime.datetime.now().isoformat(),
                    "total_resgatado": resgate.data[0]["total_resgatado"] + 1000
                }).eq("user_id", user_id).execute()
            else:
                # Cria novo registro
                self.sb.table("resgates").insert({
                    "user_id": user_id,
                    "ultimo_resgate": datetime.datetime.now().isoformat(),
                    "total_resgatado": 1000
                }).execute()
            
            # Atualiza saldo do usuário
            saldo_atual = self.get_saldo(user_id)
            self.sb.table("usuarios").update({
                "saldo": saldo_atual + 1000
            }).eq("id", user_id).execute()
            
            return True
        except Exception as e:
            print(f"Erro ao registrar resgate: {e}")
            return False
    
    def pode_resgatar_hoje(self, user_id: int):
        """Verifica se o usuário já resgatou hoje"""
        try:
            resgate = self.sb.table("resgates").select("ultimo_resgate").eq("user_id", user_id).execute()
            
            if not resgate.data:
                return True
                
            ultimo_resgate_str = resgate.data[0]["ultimo_resgate"]
            ultimo_resgate = datetime.datetime.fromisoformat(ultimo_resgate_str.replace("Z", "+00:00"))
            return ultimo_resgate.date() < datetime.datetime.now().date()
        except Exception as e:
            print(f"Erro ao verificar resgate: {e}")
            return False
        
    def set_command_channel(self, guild_id: int, channel_id: int):
        """Define o canal permitido para comandos em um servidor"""
        self.sb.table("server_config").upsert({
            "guild_id": guild_id,
            "command_channel": channel_id
        }).execute()

    def get_command_channel(self, guild_id: int):
        """Obtém o canal configurado para comandos"""
        config = self.sb.table("server_config").select("command_channel").eq("guild_id", guild_id).execute()
        return config.data[0]["command_channel"] if config.data else None
    
    def cancelar_partida(self, match_id: int):
        """Cancela uma partida e devolve as apostas"""
        try:
            apostas = self.sb.table("apostas").select("*").eq("match_id", match_id).execute().data

            for aposta in apostas:
                saldo_atual = self.get_saldo(aposta["user_id"])
                self.sb.table("usuarios").update({
                    "saldo": saldo_atual + aposta["valor"]
                }).eq("id", aposta["user_id"]).execute()

            self.sb.table("apostas").delete().eq("match_id", match_id).execute()
            self.sb.table("partidas").delete().eq("id", match_id).execute()

            return True
        except Exception as e:
            print(f"Erro ao cancelar partida: {e}")
            return False