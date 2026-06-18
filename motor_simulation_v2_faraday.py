"""
MOTOR DC COM LEI DE FARADAY E INDUTÂNCIA
Fenômenos Elétricos, Magnéticos e Oscilatórios

Autor: Projeto Engenharias 2026-1
Data: Maio 2026

Este módulo implementa o modelo completo de um motor DC incluindo:
- Lei de Faraday: ε = -dΦ/dt (tensão induzida)
- Indutância da bobina: V_L = L × dI/dt
- Força magnética: F = B × I × L_condutor
- Torque: τ = K × I
- Validação com dados medidos do carrinho RENLONG 14500

DADOS DO CARRINHO (medidos):
- Bateria: 3.7V, 500mAh, 1.85Wh
- Motor: R = 3Ω, V_carga = 3.0V
- Corrente de partida (motor travado): I ≈ 1.0A (V/R = 3.0/3.0)
- Em regime estacionário: corrente cai abaixo de 1.0A (BEMF reduz I)
- Velocidade máxima: ~5.55 m/s (20 km/h)
- Autonomia: ~35 min

NOTA SOBRE CORRENTE:
I = (V - K_e × ω) / R
Com motor travado (ω=0): I_max = 3.0/3.0 = 1.0A
Em regime (ω>0): I_regime < 1.0A (BEMF age contra a bateria)
O valor 1.0A medido corresponde à corrente de partida/carga máxima.
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.integrate import odeint
from scipy.optimize import fsolve

# ============================================================================
# PARÂMETROS DO MOTOR DC (RENLONG PEQUENO)
# ============================================================================

class MotorDCComFaraday:
    """
    Modelo eletromagnético completo de motor DC.

    Equações:
    1. Voltagem: V_entrada = I×R + L×(dI/dt) + ε_induzida
    2. Lei de Faraday: ε_induzida = K_e × ω  (tensão reversa / BEMF)
    3. Torque: τ = K_τ × I
    4. Movimento: J×(dω/dt) = τ - b×ω

    Parâmetros típicos de motor DC pequeno (escala 1:24):
    """

    def __init__(self):
        # Parâmetros elétricos
        self.R = 3.0              # Resistência da bobina (Ω) [MEDIDO]
        self.L = 0.0005           # Indutância (H) - 0.5 mH típico
        self.K_e = 0.003          # Constante de tensão (V·s/rad) [CALIBRADO: 1m em 0.3s]
        self.K_t = 0.003          # Constante de torque (N·m/A) [CALIBRADO]

        # Parâmetros mecânicos e de transmissão
        self.massa = 0.444        # Massa do carrinho (kg)
        self.raio_roda = 0.03     # Raio da roda (~3cm)
        self.reducao = 5.6        # Relação de engrenagem (Motor:Roda = 5.6:1)
        
        # Inércia equivalente refletida no motor: J_rotor + J_roda / reducao^2
        self.J_rotor = 0.00001    # Inércia interna do motor (estimativa)
        J_roda = self.massa * (self.raio_roda ** 2)
        self.J = self.J_rotor + (J_roda / (self.reducao ** 2))

        self.b = 0.000002         # Coeficiente de atrito viscoso [CALIBRADO]
        self.Phi_max = 0.005      # Fluxo magnético máximo (Wb)

        # Histórico
        self.tempo = []
        self.corrente = []
        self.velocidade = []
        self.tensao_induzida = []
        self.potencia_mecanica = []
        self.potencia_eletrica = []

    def equacoes_diferenciais(self, y, t, V_entrada):
        """
        Sistema de EDOs para motor DC com Lei de Faraday

        y = [I, ω]
        dI/dt = (V_entrada - I×R - K_e×ω) / L
        dω/dt = (K_t×I - b×ω) / J
        """
        I, omega = y

        # Lei de Faraday: tensão induzida (BEMF)
        eps_induzida = self.K_e * omega

        # Equação da corrente (Lei de Kirchhoff + Faraday)
        dI_dt = (V_entrada - I*self.R - eps_induzida) / self.L

        # Equação da velocidade angular
        torque = self.K_t * I
        d_omega_dt = (torque - self.b * omega) / self.J

        return [dI_dt, d_omega_dt]

    def simular(self, V_entrada, tempo_final=0.5, pontos=1000):
        """
        Simula resposta do motor a uma entrada de voltagem.
        Retorna: tempo, corrente, velocidade, tensão induzida
        """
        t = np.linspace(0, tempo_final, pontos)
        y0 = [0, 0]  # I=0, ω=0 inicialmente

        # Resolver EDO
        solucao = odeint(self.equacoes_diferenciais, y0, t, args=(V_entrada,))

        I = solucao[:, 0]
        omega = solucao[:, 1]

        # Calcular tensão induzida (Lei de Faraday)
        eps = self.K_e * omega

        # Potência mecânica e elétrica
        P_mec = (self.K_t * I) * omega  # Torque × velocidade angular
        P_elec = V_entrada * I           # Voltagem × corrente entrada

        # Armazenar
        self.tempo = t
        self.corrente = I
        self.velocidade = omega
        self.tensao_induzida = eps
        self.potencia_mecanica = P_mec
        self.potencia_eletrica = P_elec

        return t, I, omega, eps

    def eficiencia(self):
        """
        Calcula eficiência: P_mecânica / P_elétrica
        Medida no regime estacionário (últimos 20% do tempo),
        excluindo o transiente de aceleração — conforme prática industrial.
        """
        idx_regime = int(0.8 * len(self.potencia_mecanica))
        P_mec_media  = np.mean(self.potencia_mecanica[idx_regime:])
        P_elec_media = np.mean(self.potencia_eletrica[idx_regime:])

        if P_elec_media > 0:
            eta = (P_mec_media / P_elec_media) * 100
        else:
            eta = 0

        return eta

    def fluxo_magnetico(self):
        """Lei de Faraday: Φ = Φ_max × sin(ωt)"""
        if len(self.tempo) == 0:
            return None

        # Aproximação: fluxo varia com velocidade angular
        fluxo = self.Phi_max * np.sin(np.cumsum(self.velocidade) * 0.001)
        return fluxo

    def validar_com_dados_reais(self):
        """
        Validação com dados medidos do carrinho RENLONG

        Dados:
        - V_entrada: 3.0V (sob carga máxima)
        - I partida (ω=0): V/R = 3.0/3.0 = 1.0A
        - ω esperada: ~6.5 rad/s (0.65 m/s em roda de ~0.1m)
        - Autonomia: ~35 min
        """
        V_medido   = 3.0   # V
        I_esperado = 1.0   # A (corrente de partida com motor travado)
        v_esperado = 3.33  # m/s (medido: 1 metro em ~0.3s)

        # Simular por mais tempo (10s) para o carrinho conseguir acelerar e atingir o regime estacionário
        t, I, omega, eps = self.simular(V_medido, tempo_final=10.0)

        # Regime estacionário (últimos 20% do tempo)
        idx_regime   = int(0.8 * len(t))
        I_regime     = np.mean(I[idx_regime:])
        omega_regime = np.mean(omega[idx_regime:])

        # Converter ω_motor (rad/s) para v_carro (m/s) usando a relação de redução e raio
        omega_roda = omega_regime / self.reducao
        v_regime   = omega_roda * self.raio_roda

        print("\n" + "="*70)
        print("VALIDAÇÃO COM DADOS REAIS - CARRINHO RENLONG 14500")
        print("="*70)
        print(f"\nDados de entrada (medidos):")
        print(f"  Voltagem: {V_medido:.1f}V")
        print(f"  Corrente de partida (omega=0): I = V/R = {V_medido}/{self.R} = {V_medido/self.R:.2f}A")
        print(f"  Velocidade esperada: {v_esperado:.2f} m/s ({v_esperado * 3.6:.1f} km/h)")
        print(f"\nResultados da simulação (regime estacionário):")
        print(f"  Corrente simulada: {I_regime:.3f}A  (< {I_esperado:.1f}A pois BEMF reduz a corrente)")
        print(f"  Velocidade simulada: {v_regime:.3f} m/s ({v_regime * 3.6:.1f} km/h) (omega_motor={omega_regime:.2f}rad/s, omega_roda={omega_roda:.2f}rad/s)")
        print(f"  Tensão induzida BEMF (Faraday): {np.mean(eps[idx_regime:]):.2f}V")
        print(f"\nErros relativos (vs dados de partida):")
        print(f"  Corrente partida: {abs(I[0] - I_esperado) / I_esperado * 100:.1f}%")
        print(f"  Velocidade regime: {abs(v_regime - v_esperado) / v_esperado * 100:.1f}%")
        print(f"\nEficiência (regime estacionário): {self.eficiencia():.1f}%")
        print("="*70 + "\n")


# ============================================================================
# GRÁFICOS
# ============================================================================

def plotar_resposta_motor():
    """Plota resposta do motor a voltagem de 3V (dados reais)"""
    motor = MotorDCComFaraday()

    # Validar com dados reais — já roda simular() internamente
    motor.validar_com_dados_reais()

    # Recuperar resultados já calculados (sem rodar simular() novamente)
    t     = motor.tempo
    I     = motor.corrente
    omega = motor.velocidade
    eps   = motor.tensao_induzida

    # Velocidade linear em km/h
    v_m_s = (omega / motor.reducao) * motor.raio_roda
    v_kmh = v_m_s * 3.6

    # Plotar
    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    fig.suptitle("Motor DC com Lei de Faraday\nDados RENLONG 14500 (V=3.0V, R=3Ω)",
                 fontsize=14, fontweight='bold')

    # Corrente vs tempo
    axes[0, 0].plot(t, I, 'b-', linewidth=2)
    axes[0, 0].axhline(y=1.0, color='r', linestyle='--', alpha=0.5,
                       label='I partida = V/R = 1.0A')
    axes[0, 0].set_xlabel('Tempo (s)')
    axes[0, 0].set_ylabel('Corrente (A)')
    axes[0, 0].set_title('Corrente vs Tempo\n(cai com aumento de ω — BEMF)')
    axes[0, 0].grid(True, alpha=0.3)
    axes[0, 0].legend()

    # Velocidade linear (km/h) vs tempo
    axes[0, 1].plot(t, v_kmh, 'g-', linewidth=2)
    axes[0, 1].set_xlabel('Tempo (s)')
    axes[0, 1].set_ylabel('Velocidade (km/h)')
    axes[0, 1].set_title('Velocidade do Carrinho vs Tempo')
    axes[0, 1].grid(True, alpha=0.3)

    # Tensão induzida (Lei de Faraday / BEMF)
    axes[1, 0].plot(t, eps, 'r-', linewidth=2, label='ε = K_e × ω  (BEMF)')
    axes[1, 0].set_xlabel('Tempo (s)')
    axes[1, 0].set_ylabel('Tensão Induzida (V)')
    axes[1, 0].set_title('Lei de Faraday: Tensão Induzida vs Tempo')
    axes[1, 0].grid(True, alpha=0.3)
    axes[1, 0].legend()

    # Potência
    axes[1, 1].plot(t, motor.potencia_eletrica, 'b-', linewidth=2, label='P_elétrica')
    axes[1, 1].plot(t, motor.potencia_mecanica, 'g-', linewidth=2, label='P_mecânica')
    axes[1, 1].set_xlabel('Tempo (s)')
    axes[1, 1].set_ylabel('Potência (W)')
    axes[1, 1].set_title('Potência Elétrica vs Mecânica')
    axes[1, 1].grid(True, alpha=0.3)
    axes[1, 1].legend()

    plt.tight_layout()
    plt.savefig('./faraday_motor_response.png', dpi=300, bbox_inches='tight')
    print("Sucesso! Grafico salvo: faraday_motor_response.png")
    plt.close()


if __name__ == "__main__":
    plotar_resposta_motor()
