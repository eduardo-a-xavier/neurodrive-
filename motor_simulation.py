"""
SIMULAÇÃO DE SISTEMA MOTOR-BATERIA - CARRINHO 4X4
Disciplina: Modelagem e Simulação de Sistemas Elétricos e Magnéticos

Modelo de Motor DC simplificado com:
- Circuito elétrico (resistência, indutância)
- Dinâmica mecânica (inércia, atrito)
- Fenômenos magnéticos (torque proporcional à corrente)
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.integrate import odeint, trapezoid
from scipy.optimize import minimize

# ============================================================================
# MODELO DO MOTOR DC
# ============================================================================

class MotorDC:
    """
    Modelo simplificado de motor DC com escovas.
    
    Equações diferenciais:
    
    1) Circuito elétrico:
       V(t) - E(t) = R*i(t) + L*di/dt
       
       Onde:
       - V(t): Voltagem aplicada [V]
       - E(t): Força contra-eletromotriz (BEMF) = K_e * ω
       - i(t): Corrente [A]
       - R: Resistência interna [Ω]
       - L: Indutância [H]
       - K_e: Constante de BEMF [V·s/rad]
    
    2) Dinâmica mecânica:
       τ(t) - τ_atrito = J * dω/dt
       
       Onde:
       - τ(t) = K_t * i(t): Torque eletromagnético [N·m]
       - K_t: Constante de torque [N·m/A] (≈ K_e para motor ideal)
       - τ_atrito: Torque de atrito
       - J: Momento de inércia [kg·m²]
       - ω: Velocidade angular [rad/s]
    
    3) Atrito modelo simples:
       τ_atrito = b*ω + τ_coulomb
       
       - b: Coeficiente viscoso [N·m·s/rad]
       - τ_coulomb: Atrito Coulomb (constante) [N·m]
    """
    
    def __init__(self, R=5.0, L=0.001, K_e=0.02, J=0.0001, 
                 b_visc=0.001, tau_coulomb=0.005):
        """
        Inicializa parâmetros do motor.
        
        Args (valores típicos para motor de brinquedo):
            R: Resistência interna [Ω] - DEFAULT: 5Ω
            L: Indutância [H] - DEFAULT: 1mH (pequena, negligível às vezes)
            K_e: Constante BEMF [V·s/rad] - DEFAULT: 0.02
            J: Inércia [kg·m²] - DEFAULT: 0.1g·cm²
            b_visc: Atrito viscoso [N·m·s/rad] - DEFAULT: 0.001
            tau_coulomb: Atrito coulomb [N·m] - DEFAULT: 0.005
        """
        self.R = R
        self.L = L
        self.K_e = K_e
        self.K_t = K_e  # Para motor ideal: K_t = K_e
        self.J = J
        self.b_visc = b_visc
        self.tau_coulomb = tau_coulomb
    
    def sistema(self, estado, t, voltagem_func):
        """
        Define o sistema de equações diferenciais.
        
        estado = [i(t), ω(t)]
        - i: corrente [A]
        - ω: velocidade angular [rad/s]
        
        Retorna: [di/dt, dω/dt]
        """
        i, omega = estado
        
        # Força contra-eletromotriz
        E = self.K_e * omega
        
        # Voltagem no tempo t
        V = voltagem_func(t)
        
        # Equação elétrica: di/dt = (V - E - R*i) / L
        di_dt = (V - E - self.R * i) / self.L
        
        # Torque magnético
        tau_mag = self.K_t * i
        
        # Atrito (sempre opõe movimento)
        if abs(omega) > 0.01:  # Se motor está girando
            tau_atrito = self.b_visc * omega + np.sign(omega) * self.tau_coulomb
        else:
            tau_atrito = 0
        
        # Equação mecânica: dω/dt = (τ_mag - τ_atrito) / J
        d_omega_dt = (tau_mag - tau_atrito) / self.J
        
        return [di_dt, d_omega_dt]
    
    def simular(self, voltagem, tempo, estado_inicial=[0, 0]):
        """
        Simula o motor com voltagem constante.
        
        Args:
            voltagem: Voltagem aplicada [V] (pode ser float ou array)
            tempo: Vetor de tempo [s]
            estado_inicial: [i0, omega0]
        
        Retorna:
            tempo: Vetor de tempo
            corrente: Corrente ao longo do tempo [A]
            omega: Velocidade angular [rad/s]
            velocidade_linear: Velocidade linear [m/s] (com raio de roda)
        """
        
        # Se voltagem for escalar, cria função
        if np.isscalar(voltagem):
            V_func = lambda t: voltagem
        else:
            # Se for array, interpola
            V_func = lambda t: np.interp(t, tempo, voltagem)
        
        # Resolve ODE
        solucao = odeint(self.sistema, estado_inicial, tempo, args=(V_func,))
        
        corrente = solucao[:, 0]
        omega = solucao[:, 1]
        
        # Converte para velocidade linear (m/s)
        # Raio típico da roda: 2.2 cm = 0.022 m
        raio_roda = 0.022  # metros
        velocidade_linear = omega * raio_roda
        
        return tempo, corrente, omega, velocidade_linear
    
    def potencia_mecanica(self, corrente, omega):
        """Potência mecânica (watts) = Torque * velocidade angular"""
        torque = self.K_t * corrente
        return torque * omega
    
    def potencia_eletrica(self, voltagem, corrente):
        """Potência elétrica (watts) = V * I"""
        return voltagem * corrente
    
    def eficiencia(self, voltagem, corrente, omega):
        """Eficiência do motor = P_mec / P_elec"""
        p_mec = np.abs(self.potencia_mecanica(corrente, omega))
        p_elec = np.abs(self.potencia_eletrica(voltagem, corrente))
        # Evita divisão por zero
        return np.where(p_elec > 0.01, p_mec / p_elec, 0)


# ============================================================================
# SIMULAÇÕES
# ============================================================================

def plot_simulacao_basica():
    """Simula motor com diferentes voltagens e mostra resposta."""
    
    print("\n" + "="*70)
    print("SIMULAÇÃO 1: Resposta do Motor a Diferentes Voltagens")
    print("="*70)
    
    motor = MotorDC()
    tempo = np.linspace(0, 2, 1000)  # 2 segundos
    
    fig, axes = plt.subplots(3, 1, figsize=(12, 10))
    
    voltagens = [3, 4.8, 6]
    cores = ['blue', 'green', 'red']
    
    for V, cor in zip(voltagens, cores):
        print(f"\nSimulando com V = {V}V...")
        t, i, omega, v_linear = motor.simular(V, tempo)
        
        axes[0].plot(t, i, label=f'{V}V', color=cor, linewidth=2)
        axes[1].plot(t, omega, label=f'{V}V', color=cor, linewidth=2)
        axes[2].plot(t, v_linear * 3.6, label=f'{V}V (≈{v_linear[-1]*3.6:.1f} km/h)', 
                    color=cor, linewidth=2)  # Converte m/s para km/h
    
    axes[0].set_ylabel('Corrente [A]', fontsize=11)
    axes[0].set_title('Resposta do Motor DC a Diferentes Voltagens', fontsize=13, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()
    
    axes[1].set_ylabel('Velocidade Angular [rad/s]', fontsize=11)
    axes[1].grid(True, alpha=0.3)
    axes[1].legend()
    
    axes[2].set_ylabel('Velocidade Linear [km/h]', fontsize=11)
    axes[2].set_xlabel('Tempo [s]', fontsize=11)
    axes[2].grid(True, alpha=0.3)
    axes[2].legend()
    
    plt.tight_layout()
    plt.savefig('./simulacao_1_voltagens.png', dpi=150, bbox_inches='tight')
    print("✓ Gráfico salvo: simulacao_1_voltagens.png")
    plt.close()


def plot_efeito_atrito():
    """Mostra efeito do atrito na velocidade máxima."""
    
    print("\n" + "="*70)
    print("SIMULAÇÃO 2: Efeito do Atrito na Resposta do Motor")
    print("="*70)
    
    tempo = np.linspace(0, 3, 1000)
    
    fig, axes = plt.subplots(2, 2, figsize=(13, 10))
    
    # Motor com diferentes níveis de atrito
    configs = [
        {"b_visc": 0.0001, "tau_coulomb": 0.001, "label": "Atrito baixo"},
        {"b_visc": 0.001, "tau_coulomb": 0.005, "label": "Atrito médio"},
        {"b_visc": 0.005, "tau_coulomb": 0.015, "label": "Atrito alto"},
    ]
    
    for config in configs:
        motor = MotorDC(b_visc=config["b_visc"], tau_coulomb=config["tau_coulomb"])
        t, i, omega, v_linear = motor.simular(4.8, tempo)
        
        label = f"{config['label']}: {v_linear[-1]*3.6:.1f} km/h"
        
        axes[0, 0].plot(t, i, label=label, linewidth=2)
        axes[0, 1].plot(t, omega, label=label, linewidth=2)
        axes[1, 0].plot(t, v_linear * 3.6, label=label, linewidth=2)
        
        # Potência
        p_mec = motor.potencia_mecanica(i, omega)
        axes[1, 1].plot(t, p_mec, label=label, linewidth=2)
    
    axes[0, 0].set_ylabel('Corrente [A]', fontsize=10)
    axes[0, 0].set_title('Corrente vs Tempo', fontsize=11, fontweight='bold')
    axes[0, 0].grid(True, alpha=0.3)
    axes[0, 0].legend(fontsize=9)
    
    axes[0, 1].set_ylabel('Velocidade Angular [rad/s]', fontsize=10)
    axes[0, 1].set_title('Velocidade Angular vs Tempo', fontsize=11, fontweight='bold')
    axes[0, 1].grid(True, alpha=0.3)
    axes[0, 1].legend(fontsize=9)
    
    axes[1, 0].set_ylabel('Velocidade Linear [km/h]', fontsize=10)
    axes[1, 0].set_title('Velocidade Linear vs Tempo (4.8V)', fontsize=11, fontweight='bold')
    axes[1, 0].grid(True, alpha=0.3)
    axes[1, 0].legend(fontsize=9)
    
    axes[1, 1].set_ylabel('Potência Mecânica [W]', fontsize=10)
    axes[1, 1].set_title('Potência Mecânica vs Tempo', fontsize=11, fontweight='bold')
    axes[1, 1].set_xlabel('Tempo [s]', fontsize=10)
    axes[1, 1].grid(True, alpha=0.3)
    axes[1, 1].legend(fontsize=9)
    
    plt.tight_layout()
    plt.savefig('./simulacao_2_atrito.png', dpi=150, bbox_inches='tight')
    print("✓ Gráfico salvo: simulacao_2_atrito.png")
    plt.close()


def plot_eficiencia():
    """Analisa eficiência do motor em diferentes condições."""
    
    print("\n" + "="*70)
    print("SIMULAÇÃO 3: Análise de Eficiência do Motor")
    print("="*70)
    
    motor = MotorDC()
    tempo = np.linspace(0, 2, 500)
    
    fig, axes = plt.subplots(2, 2, figsize=(13, 10))
    
    voltagens = [3, 4.8, 6]
    cores = ['blue', 'green', 'red']
    
    for V, cor in zip(voltagens, cores):
        t, i, omega, v_linear = motor.simular(V, tempo)
        
        p_elec = motor.potencia_eletrica(V, i)
        p_mec = motor.potencia_mecanica(i, omega)
        eficiencia = motor.eficiencia(V, i, omega)
        
        # Remove valores iniciais quando motor está acelerando
        inicio = 100
        
        axes[0, 0].plot(t[inicio:], p_elec[inicio:], label=f'{V}V', color=cor, linewidth=2)
        axes[0, 1].plot(t[inicio:], p_mec[inicio:], label=f'{V}V', color=cor, linewidth=2)
        axes[1, 0].plot(t[inicio:], eficiencia[inicio:]*100, label=f'{V}V', color=cor, linewidth=2)
        
        # Consumo energético total
        energia_elec = trapezoid(p_elec, t)
        energia_mec = trapezoid(p_mec, t)
        eff_media = (energia_mec / energia_elec) * 100 if energia_elec > 0 else 0
        
        axes[1, 1].bar(V, eff_media, color=cor, alpha=0.7, label=f'{V}V: {eff_media:.1f}%')
    
    axes[0, 0].set_ylabel('Potência Elétrica [W]', fontsize=10)
    axes[0, 0].set_title('Potência Elétrica Consumida', fontsize=11, fontweight='bold')
    axes[0, 0].grid(True, alpha=0.3)
    axes[0, 0].legend()
    
    axes[0, 1].set_ylabel('Potência Mecânica [W]', fontsize=10)
    axes[0, 1].set_title('Potência Mecânica Produzida', fontsize=11, fontweight='bold')
    axes[0, 1].grid(True, alpha=0.3)
    axes[0, 1].legend()
    
    axes[1, 0].set_ylabel('Eficiência [%]', fontsize=10)
    axes[1, 0].set_xlabel('Tempo [s]', fontsize=10)
    axes[1, 0].set_title('Eficiência do Motor (P_mec / P_elec)', fontsize=11, fontweight='bold')
    axes[1, 0].grid(True, alpha=0.3)
    axes[1, 0].legend()
    axes[1, 0].set_ylim([0, 100])
    
    axes[1, 1].set_ylabel('Eficiência Média [%]', fontsize=10)
    axes[1, 1].set_xlabel('Voltagem [V]', fontsize=10)
    axes[1, 1].set_title('Eficiência Média vs Voltagem', fontsize=11, fontweight='bold')
    axes[1, 1].grid(True, alpha=0.3, axis='y')
    axes[1, 1].legend(fontsize=9)
    axes[1, 1].set_ylim([0, 100])
    
    plt.tight_layout()
    plt.savefig('./simulacao_3_eficiencia.png', dpi=150, bbox_inches='tight')
    print("✓ Gráfico salvo: simulacao_3_eficiencia.png")
    plt.close()


def calibracao_com_dados_reais():
    """
    ESTA FUNÇÃO MOSTRA COMO CALIBRAR O MODELO COM DADOS REAIS DO CARRINHO.
    
    Para usar:
    1. Meça o carrinho com um smartphone/cronômetro: quanto tempo leva pra atingir velocidade máxima?
    2. Meça voltagem da bateria (multímetro)
    3. Preencha os dados em "dados_reais" abaixo
    4. Descomente e rode esta função
    """
    
    print("\n" + "="*70)
    print("CALIBRAÇÃO COM DADOS REAIS")
    print("="*70)
    
    # *** PREENCHA COM SEUS DADOS MEDIDOS ***
    dados_reais = {
        "voltagem_medida": 4.8,      # V (meça com multímetro)
        "tempo_aceleracao": 1.5,     # segundos (quanto tempo pra atingir max speed)
        "velocidade_max": 20/3.6,    # m/s (converter de km/h para m/s: 20 km/h ≈ 5.56 m/s)
    }
    
    print("\nDados coletados do carrinho:")
    print(f"  Voltagem: {dados_reais['voltagem_medida']} V")
    print(f"  Tempo até velocidade máxima: {dados_reais['tempo_aceleracao']} s")
    print(f"  Velocidade máxima: {dados_reais['velocidade_max']*3.6:.1f} km/h")
    
    # Função custo para otimização
    def custo_calibracao(params):
        """Minimiza diferença entre simulação e dados reais."""
        b_visc, tau_coulomb = params
        if b_visc < 0 or tau_coulomb < 0:
            return 1e10
        
        motor = MotorDC(b_visc=b_visc, tau_coulomb=tau_coulomb)
        tempo = np.linspace(0, 3, 500)
        _, _, omega, v_linear = motor.simular(dados_reais["voltagem_medida"], tempo)
        
        # Velocity no tempo medido
        idx_tempo = np.argmin(np.abs(tempo - dados_reais["tempo_aceleracao"]))
        v_sim = v_linear[idx_tempo]
        
        # Velocity máxima (estado estacionário)
        v_max_sim = v_linear[-1]
        
        # Erro: diferença entre simulado e real
        erro = (v_sim - dados_reais["velocidade_max"])**2 + \
               (v_max_sim - dados_reais["velocidade_max"])**2
        
        return erro
    
    # Otimiza parâmetros
    print("\nOtimizando parâmetros de atrito...")
    resultado = minimize(custo_calibracao, [0.001, 0.005], method='Nelder-Mead')
    
    b_otimizado, tau_otimizado = resultado.x
    
    print(f"\nParâmetros otimizados:")
    print(f"  Atrito viscoso (b_visc): {b_otimizado:.6f} N·m·s/rad")
    print(f"  Atrito Coulomb (tau_coulomb): {tau_otimizado:.6f} N·m")
    
    # Simula com parâmetros otimizados
    motor_calibrado = MotorDC(b_visc=b_otimizado, tau_coulomb=tau_otimizado)
    tempo = np.linspace(0, 3, 500)
    _, _, omega, v_linear = motor_calibrado.simular(dados_reais["voltagem_medida"], tempo)
    
    print(f"\nValidação:")
    idx_tempo = np.argmin(np.abs(tempo - dados_reais["tempo_aceleracao"]))
    print(f"  Velocidade simulada em {dados_reais['tempo_aceleracao']}s: {v_linear[idx_tempo]*3.6:.2f} km/h")
    print(f"  Velocidade máxima simulada: {v_linear[-1]*3.6:.2f} km/h")
    print(f"  Velocidade máxima medida: {dados_reais['velocidade_max']*3.6:.2f} km/h")
    
    return motor_calibrado


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("MODELAGEM E SIMULAÇÃO DE MOTOR DC - CARRINHO 4X4")
    print("="*70)
    
    # Roda as simulações
    plot_simulacao_basica()
    plot_efeito_atrito()
    plot_eficiencia()
    
    # Descomente para calibrar com dados reais
    # motor_calibrado = calibracao_com_dados_reais()
    
    print("\n" + "="*70)
    print("✓ Simulações concluídas! Verifique os gráficos gerados.")
    print("="*70)
    print("\nPróximos passos:")
    print("1. Meça a velocidade máxima e tempo de aceleração do carrinho")
    print("2. Preencha os dados em 'calibracao_com_dados_reais()'")
    print("3. Descomente a função no final do código e rode novamente")
    print("4. Simule cenários diferentes (aumentar atrito, etc)")
