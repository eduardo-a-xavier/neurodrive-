"""
ANÁLISE DE BATERIA E CONSUMO ENERGÉTICO
Disciplina: Fenômenos Elétricos, Magnéticos e Oscilatórios

Modela comportamento de bateria Li-po com dados reais do carrinho Kizumba.
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.integrate import odeint

# ============================================================================
# DADOS REAIS DA BATERIA
# ============================================================================

BATERIA = {
    "voltagem_nominal": 3.7,      # V (Li-po 1S)
    "energia_total": 1.85,         # Wh
    "capacidade_mah": 500,        # mAh
    "resistencia_interna": 0.5,    # Ω (estimativa para Li-po)
}

print("\n" + "="*70)
print("ANÁLISE DE BATERIA - CARRINHO KIZUMBA 4X4")
print("="*70)

print(f"\nEspecificações da bateria:")
print(f"  Voltagem nominal: {BATERIA['voltagem_nominal']} V")
print(f"  Energia total: {BATERIA['energia_total']} Wh")
print(f"  Capacidade: {BATERIA['capacidade_mah']} mAh")
print(f"  Resistência interna (estimada): {BATERIA['resistencia_interna']} Ω")

# ============================================================================
# CÁLCULOS BÁSICOS
# ============================================================================

capacidade_ah = BATERIA['capacidade_mah'] / 1000
capacidade_coulombs = capacidade_ah * 3600

print(f"\nConversões:")
print(f"  Capacidade: {capacidade_ah} Ah = {capacidade_coulombs:.0f} C (Coulombs)")

# ============================================================================
# TEMPO DE FUNCIONAMENTO vs CORRENTE
# ============================================================================

print(f"\n" + "="*70)
print("TEMPO DE FUNCIONAMENTO TEÓRICO")
print("="*70)
print(f"\nPara funcionamento contínuo (Lei de Peukert simplificada):")
print(f"{'Corrente':>12} {'Potência':>12} {'Tempo':>15} {'Ciclo':>12}")
print(f"{'-'*12} {'-'*12} {'-'*15} {'-'*12}")

correntes = np.array([0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5])

for I in correntes:
    tempo_horas = capacidade_ah / I
    tempo_minutos = tempo_horas * 60
    
    potencia = BATERIA['voltagem_nominal'] * I
    
    # Ciclo de funcionamento (% de capacidade por minuto)
    if tempo_minutos > 0:
        ciclo = 100 / tempo_minutos
    else:
        ciclo = 0
    
    print(f"{I:>10.2f}A {potencia:>10.2f}W {tempo_minutos:>12.1f} min {ciclo:>10.2f}%/min")

# ============================================================================
# MODELO DE DESCARGA DE BATERIA COM CORRENTE VARIÁVEL
# ============================================================================

class ModeloBateria:
    """
    Modelo simplificado de bateria Li-po.
    
    Considera:
    - Queda de voltagem com corrente (resistência interna)
    - Descarga não-linear (efeito Peukert)
    - Voltagem mínima operacional (cutoff)
    """
    
    def __init__(self, V_nom=3.7, E_total=1.85, R_int=0.5, V_cutoff=2.5):
        """
        V_nom: Voltagem nominal [V]
        E_total: Energia total [Wh]
        R_int: Resistência interna [Ω]
        V_cutoff: Voltagem mínima [V]
        """
        self.V_nom = V_nom
        self.E_total = E_total
        self.R_int = R_int
        self.V_cutoff = V_cutoff
        self.Q_total = (E_total / V_nom) * 3600  # Carga em Coulombs
        self.Q_discharged = 0  # Carga descarregada
    
    def voltagem(self, corrente):
        """
        Calcula voltagem terminal com queda resistiva.
        V_terminal = V_oc - R_int * I
        """
        # Voltagem de circuito aberto (aproximada)
        SOC = 1 - (self.Q_discharged / self.Q_total)  # State of Charge
        
        # Li-po: voltagem varia ~3.0V (vazio) a ~4.2V (cheio)
        # Simplificado: linear entre 3.0V e 4.2V
        V_oc = 3.0 + (4.2 - 3.0) * SOC
        
        # Queda resistiva
        V_terminal = V_oc - self.R_int * corrente
        
        return V_terminal, V_oc
    
    def descarga_step(self, corrente, dt):
        """
        Avança simulação em dt segundos com corrente I.
        """
        if self.Q_discharged >= self.Q_total:
            return None  # Bateria vazia
        
        # Descarga em Coulombs
        dQ = corrente * dt
        self.Q_discharged += dQ
        
        # Garante não ultrapassar capacidade
        if self.Q_discharged > self.Q_total:
            self.Q_discharged = self.Q_total
        
        V_terminal, V_oc = self.voltagem(corrente)
        
        # Energia consumida
        energia = V_terminal * corrente * dt / 3600  # Wh
        
        return {
            'V_terminal': V_terminal,
            'V_oc': V_oc,
            'energia': energia,
            'SOC': 1 - (self.Q_discharged / self.Q_total)
        }

# ============================================================================
# SIMULAÇÃO DE DESCARGA
# ============================================================================

print(f"\n" + "="*70)
print("SIMULAÇÃO DE DESCARGA COM CORRENTE VARIÁVEL")
print("="*70)

# Scenario 1: Corrente constante
bateria = ModeloBateria()
tempo = []
V_terminal = []
V_oc = []
SOC = []
energia_consumida_total = 0

corrente_constante = 0.5  # A

print(f"\nCenário 1: Corrente constante de {corrente_constante}A")

t = 0
dt = 0.1  # 0.1 segundos
while True:
    resultado = bateria.descarga_step(corrente_constante, dt)
    if resultado is None:
        break
    
    tempo.append(t)
    V_terminal.append(resultado['V_terminal'])
    V_oc.append(resultado['V_oc'])
    SOC.append(resultado['SOC'])
    energia_consumida_total += resultado['energia']
    
    t += dt
    
    if t > 3600:  # Limite 1 hora
        break

tempo = np.array(tempo)
V_terminal = np.array(V_terminal)
SOC = np.array(SOC)

print(f"  Tempo total: {tempo[-1]/60:.1f} minutos")
print(f"  Energia consumida: {energia_consumida_total:.2f} Wh")
print(f"  Voltagem final: {V_terminal[-1]:.2f}V")

# Scenario 2: Corrente variável (simulando aceleração + regime constante)
bateria2 = ModeloBateria()
tempo2 = []
V_terminal2 = []
corrente_sim = []
SOC2 = []

print(f"\nCenário 2: Corrente variável (aceleração + regime)")

t = 0
dt = 0.1
while True:
    # Primeiro 1 segundo: aceleração (I = 0.8A)
    # Depois: regime constante (I = 0.3A)
    if t < 1.0:
        I = 0.8
    else:
        I = 0.3
    
    resultado = bateria2.descarga_step(I, dt)
    if resultado is None:
        break
    
    tempo2.append(t)
    V_terminal2.append(resultado['V_terminal'])
    corrente_sim.append(I)
    SOC2.append(resultado['SOC'])
    
    t += dt
    
    if t > 3600:
        break

tempo2 = np.array(tempo2)
V_terminal2 = np.array(V_terminal2)

print(f"  Tempo total: {tempo2[-1]/60:.1f} minutos")
print(f"  Voltagem final: {V_terminal2[-1]:.2f}V")

# ============================================================================
# GRÁFICOS
# ============================================================================

fig, axes = plt.subplots(2, 2, figsize=(13, 10))

# Gráfico 1: Voltagem vs Tempo (corrente constante)
axes[0, 0].plot(tempo/60, V_terminal, 'b-', linewidth=2, label='V_terminal')
axes[0, 0].axhline(y=BATERIA['voltagem_nominal'], color='g', linestyle='--', 
                   label='V_nominal', alpha=0.7)
axes[0, 0].axhline(y=2.5, color='r', linestyle='--', label='Cutoff (2.5V)', alpha=0.7)
axes[0, 0].set_ylabel('Voltagem [V]', fontsize=11)
axes[0, 0].set_title(f'Descarga com Corrente Constante ({corrente_constante}A)', fontsize=12, fontweight='bold')
axes[0, 0].grid(True, alpha=0.3)
axes[0, 0].legend()
axes[0, 0].set_ylim([2.0, 4.5])

# Gráfico 2: State of Charge
axes[0, 1].plot(tempo/60, SOC*100, 'g-', linewidth=2.5)
axes[0, 1].set_ylabel('State of Charge (%)', fontsize=11)
axes[0, 1].set_title('Nível de Carga da Bateria', fontsize=12, fontweight='bold')
axes[0, 1].grid(True, alpha=0.3)
axes[0, 1].set_ylim([0, 105])

# Gráfico 3: Corrente e Voltagem (cenário variável)
ax1 = axes[1, 0]
ax2 = ax1.twinx()

line1 = ax1.plot(tempo2/60, corrente_sim, 'r-', linewidth=2.5, label='Corrente')
ax1.set_ylabel('Corrente [A]', fontsize=11, color='r')
ax1.tick_params(axis='y', labelcolor='r')
ax1.set_ylim([0, 1.0])

line2 = ax2.plot(tempo2/60, V_terminal2, 'b-', linewidth=2.5, label='Voltagem')
ax2.set_ylabel('Voltagem [V]', fontsize=11, color='b')
ax2.tick_params(axis='y', labelcolor='b')
ax2.set_ylim([2.0, 4.5])

ax1.set_xlabel('Tempo [minutos]', fontsize=11)
ax1.set_title('Cenário com Aceleração + Regime Constante', fontsize=12, fontweight='bold')
ax1.grid(True, alpha=0.3)

# Gráfico 4: State of Charge (variável)
axes[1, 1].plot(tempo2/60, np.array(SOC2)*100, 'g-', linewidth=2.5)
axes[1, 1].set_ylabel('State of Charge (%)', fontsize=11)
axes[1, 1].set_xlabel('Tempo [minutos]', fontsize=11)
axes[1, 1].set_title('Nível de Carga - Cenário Variável', fontsize=12, fontweight='bold')
axes[1, 1].grid(True, alpha=0.3)
axes[1, 1].set_ylim([0, 105])

plt.tight_layout()
plt.savefig('analise_bateria.png', dpi=150, bbox_inches='tight')
print(f"\n✓ Gráfico salvo: analise_bateria.png")
plt.close()

# ============================================================================
# RECOMENDAÇÕES
# ============================================================================

print("\n" + "="*70)
print("RECOMENDAÇÕES PARA COLETA DE DADOS")
print("="*70)

print("""
Para CALIBRAR a simulação com dados reais, você PRECISA medir:

1. VOLTAGEM REAL DA BATERIA (Essencial):
   - Use um multímetro em modo "Voltagem DC"
   - Meça com carrinho parado
   - Meça durante aceleração máxima
   - Anote a voltagem inicial e após usar por 10 minutos

2. AUTONOMIA DO CARRINHO:
   - Cronômetro: quanto tempo o carrinho funciona até parar?
   - Isso permite calcular corrente média: I_média = capacidade / tempo

3. VELOCIDADE E ACELERAÇÃO:
   - Video em 60fps: cronometra quanto tempo leva pra atingir velocidade máxima
   - Distância em 1 segundo: meça com régua/fita métrica
   - Isso valida a simulação de dinâmica do motor

4. CORRENTE CONSUMIDA (Ideal):
   - Multímetro em série na bateria (desconecta um fio, insere multímetro)
   - Corrente parado (só fricção)
   - Corrente acelerando (máximo)
   - Corrente em regime constante

5. CONSUMO DE ENERGIA:
   - Cálculo: E = Integral(V * I * dt)
   - Compare: energia teórica vs energia medida
   
Com esses dados, você consegue:
  ✓ Validar que o modelo está correto
  ✓ Prever autonomia em diferentes cenários
  ✓ Explicar perdas de energia (dissipação térmica)
  ✓ Fazer relatório técnico sólido para a UC
""")

print("="*70)
