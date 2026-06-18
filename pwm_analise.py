"""
ANÁLISE PWM - MODULAÇÃO POR LARGURA DE PULSO
Fenômenos Elétricos, Magnéticos e Oscilatórios

Autor: Projeto Engenharias 2026-1
Data: Maio 2026

Este módulo analisa PWM (Pulse Width Modulation):
- Voltagem média: V_média = V_máx × (Duty Cycle / 100%)
- Frequência de chaveamento: f_PWM (típico: 1-50 kHz)
- Período: T = 1/f_PWM
- Aplicação: controle de velocidade/potência do motor RC

Fórmulas:
1. Voltagem média: V_avg = V_max × D, onde D = duty cycle (0-1)
2. Corrente média: I_avg = V_avg / R
3. Potência: P = V_avg × I_avg
4. Ripple de corrente: ΔI = (V_max - I×R) × T_on / L
   onde T_on = D × T (tempo ligado)

Equações diferenciais com PWM:
dI/dt = (V_chaveada - I×R - K_e×ω) / L  [Lei de Faraday + PWM]
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.integrate import odeint

# ============================================================================
# GERAÇÃO E ANÁLISE DE SINAIS PWM
# ============================================================================

class ControladorPWM:
    """
    Simula PWM e seu efeito na corrente/velocidade do motor.
    """
    
    def __init__(self, V_max=3.7, f_pwm=5000, R_motor=3.0, L_motor=0.0005, K_e=0.02):
        """
        Inicializa controlador PWM.
        
        Args:
            V_max: voltagem máxima (V)
            f_pwm: frequência PWM (Hz)
            R_motor: resistência motor (Ω)
            L_motor: indutância motor (H)
            K_e: constante de força eletromotriz (V·s/rad)
        """
        self.V_max = V_max
        self.f_pwm = f_pwm
        self.T_pwm = 1 / f_pwm  # Período PWM
        
        # Parâmetros do motor
        self.R = R_motor
        self.L = L_motor
        self.K_e = K_e
    
    def gerar_onda_pwm(self, duty_cycle, tempo_total=None, num_periodos=10):
        """
        Gera sinal PWM.
        
        Args:
            duty_cycle: 0-100 (%)
            tempo_total: duração total (s) - se None, usa num_periodos
            num_periodos: número de períodos PWM
        
        Retorna:
            tempo, sinal_pwm
        """
        if tempo_total is None:
            tempo_total = num_periodos * self.T_pwm
        
        # Resolução: 10 pontos por período PWM (ou mais)
        dt = self.T_pwm / 100
        t = np.arange(0, tempo_total, dt)
        
        # Sinal PWM (trem de pulsos)
        sinal = np.zeros_like(t)
        D = duty_cycle / 100.0
        
        for i, time in enumerate(t):
            tempo_no_periodo = time % self.T_pwm
            if tempo_no_periodo < D * self.T_pwm:
                sinal[i] = self.V_max
            else:
                sinal[i] = 0
        
        return t, sinal
    
    def tensao_media_pwm(self, duty_cycle):
        """Calcula tensão média: V_avg = V_max × D"""
        return self.V_max * (duty_cycle / 100.0)
    
    def corrente_media_esperada(self, duty_cycle):
        """Corrente média esperada em regime estacionário"""
        V_avg = self.tensao_media_pwm(duty_cycle)
        return V_avg / self.R
    
    def potencia_media(self, duty_cycle):
        """Potência média dissipada no motor"""
        V_avg = self.tensao_media_pwm(duty_cycle)
        I_avg = self.corrente_media_esperada(duty_cycle)
        return V_avg * I_avg
    
    def ripple_corrente(self, duty_cycle, omega=0):
        """
        Estima ripple de corrente (variação cíclica).
        
        ΔI ≈ (V_max - I_med×R) × T_on / L
        onde T_on = (D × T_PWM)
        """
        V_avg = self.tensao_media_pwm(duty_cycle)
        I_avg = V_avg / self.R
        
        # Voltagem efetiva para di/dt
        V_efetiva = self.V_max - I_avg * self.R - self.K_e * omega
        
        T_on = (duty_cycle / 100.0) * self.T_pwm
        
        if self.L > 0:
            delta_I = V_efetiva * T_on / self.L
        else:
            delta_I = 0
        
        return delta_I
    
    def simular_resposta_pwm(self, duty_cycle, tempo_total=0.05):
        """
        Simula resposta da corrente com PWM (aproximação com voltagem média).
        
        Para simplificar, usa V_média em vez de chaveamento rápido.
        """
        V_avg = self.tensao_media_pwm(duty_cycle)
        
        # EDO simples: dI/dt = (V_avg - I×R) / L
        def eqn(I, t):
            return (V_avg - I * self.R) / self.L
        
        t = np.linspace(0, tempo_total, 1000)
        I = odeint(eqn, 0, t)
        
        return t, I.flatten()
    
    def imprimir_analise_pwm(self, duty_cycle):
        """Imprime análise do PWM"""
        V_avg = self.tensao_media_pwm(duty_cycle)
        I_avg = self.corrente_media_esperada(duty_cycle)
        P_avg = self.potencia_media(duty_cycle)
        ripple = self.ripple_corrente(duty_cycle, omega=0)
        
        print("\n" + "="*70)
        print("ANÁLISE PWM - CONTROLE DE MOTOR")
        print("="*70)
        print(f"\nParâmetros PWM:")
        print(f"  Voltagem máxima: {self.V_max:.1f}V")
        print(f"  Frequência PWM: {self.f_pwm/1e3:.1f} kHz (período = {self.T_pwm*1e6:.1f}µs)")
        print(f"  Duty Cycle: {duty_cycle:.1f}%")
        print(f"\nResultados (regime estacionário):")
        print(f"  Tensão média: V_avg = {V_avg:.2f}V")
        print(f"  Corrente média: I_avg = {I_avg:.3f}A")
        print(f"  Potência média: P_avg = {P_avg:.3f}W")
        print(f"  Ripple de corrente: ΔI ≈ {ripple:.4f}A")
        print(f"\nInterpretação:")
        print(f"  - Duty cycle de {duty_cycle:.0f}% → V_média de {V_avg:.2f}V")
        print(f"  - Isso corresponde a ~{(duty_cycle/100)*100:.0f}% da potência máxima")
        print("="*70 + "\n")


# ============================================================================
# GRÁFICOS
# ============================================================================

def plotar_pwm_analise():
    """Plota análise completa de PWM"""
    
    # Criar controlador
    pwm = ControladorPWM(V_max=3.0, f_pwm=5000, R_motor=3.0, L_motor=0.0005)
    
    # Duty cycles para testar
    duty_cycles = [25, 50, 75, 100]
    
    # Gerar ondas PWM
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    fig.suptitle("Análise PWM - Modulação por Largura de Pulso\nCarrinho RENLONG (V_max=3.0V, f_PWM=5kHz)", 
                 fontsize=14, fontweight='bold')
    
    colors = ['b', 'g', 'r', 'orange']
    
    # 1. Ondas PWM comparadas
    ax = axes[0, 0]
    for dc, color in zip(duty_cycles, colors):
        t, pwm_signal = pwm.gerar_onda_pwm(dc, num_periodos=3)
        ax.plot(t*1e6, pwm_signal, label=f'DC={dc}%', color=color, linewidth=2, alpha=0.7)
    
    ax.set_xlabel('Tempo (µs)')
    ax.set_ylabel('Voltagem (V)')
    ax.set_title('Sinais PWM (primeiros 3 períodos)')
    ax.grid(True, alpha=0.3)
    ax.legend(loc='upper right')
    
    # 2. Tensão média vs Duty Cycle
    ax = axes[0, 1]
    dc_range = np.linspace(0, 100, 101)
    V_avg = [pwm.tensao_media_pwm(dc) for dc in dc_range]
    
    ax.plot(dc_range, V_avg, 'b-', linewidth=2)
    ax.fill_between(dc_range, 0, V_avg, alpha=0.3)
    ax.scatter(duty_cycles, [pwm.tensao_media_pwm(dc) for dc in duty_cycles], 
               color='r', s=100, zorder=5)
    ax.set_xlabel('Duty Cycle (%)')
    ax.set_ylabel('Tensão Média (V)')
    ax.set_title('Relação Linear: V_média = V_max × D')
    ax.grid(True, alpha=0.3)
    
    # 3. Corrente média vs Duty Cycle
    ax = axes[1, 0]
    I_avg = [pwm.corrente_media_esperada(dc) for dc in dc_range]
    P_avg = [pwm.potencia_media(dc) for dc in dc_range]
    
    ax.plot(dc_range, I_avg, 'g-', linewidth=2, label='Corrente média')
    ax.scatter(duty_cycles, [pwm.corrente_media_esperada(dc) for dc in duty_cycles], 
               color='r', s=100, zorder=5)
    ax.set_xlabel('Duty Cycle (%)')
    ax.set_ylabel('Corrente Média (A)')
    ax.set_title('Corrente Média vs Duty Cycle')
    ax.grid(True, alpha=0.3)
    ax.legend()
    
    # 4. Potência vs Duty Cycle
    ax = axes[1, 1]
    ax.plot(dc_range, P_avg, 'r-', linewidth=2)
    ax.fill_between(dc_range, 0, P_avg, alpha=0.3, color='r')
    ax.scatter(duty_cycles, [pwm.potencia_media(dc) for dc in duty_cycles], 
               color='b', s=100, zorder=5)
    ax.set_xlabel('Duty Cycle (%)')
    ax.set_ylabel('Potência Média (W)')
    ax.set_title('Potência Dissipada vs Duty Cycle (P = V²/R)')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('./pwm_analise.png', dpi=300, bbox_inches='tight')
    print("✓ Gráfico salvo: pwm_analise.png")
    plt.close()
    
    # Imprimir análises para cada duty cycle
    print("\nANÁLISE DETALHADA DE PWM PARA CADA DUTY CYCLE:")
    print("="*70)
    for dc in duty_cycles:
        pwm.imprimir_analise_pwm(dc)


if __name__ == "__main__":
    plotar_pwm_analise()
