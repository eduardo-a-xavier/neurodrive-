"""
CIRCUITO RLC E RESSONÂNCIA
Fenômenos Elétricos, Magnéticos e Oscilatórios

Autor: Projeto Engenharias 2026-1
Data: Maio 2026

Este módulo analisa oscilações em circuitos RLC:
- Frequência natural: f₀ = 1/(2π√LC)
- Fator de amortecimento: ζ = R/(2√(L/C))
- Resposta: sub-amortecida, criticamente amortecida, sobre-amortecida
- Ressonância: Q = ω₀L/R
- Aplicação: circuito LC do motor + capacitor de filtro da bateria

CONTEXTO DO CARRINHO:
- Motor tem indutância L ≈ 0.5 mH
- Circuito tem resistência R = 3Ω (motor)
- Capacitor de filtro típico: C ≈ 100 µF
- Frequência natural esperada: ~225 Hz
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.integrate import odeint

# ============================================================================
# PARÂMETROS DO CIRCUITO RLC
# ============================================================================

class CircuitoRLC:
    """
    Circuito RLC série com análise de ressonância e amortecimento.
    
    Equações:
    1. Voltagem: V_in = I×R + L×(dI/dt) + V_C
    2. Capacitor: I = C×(dV_C/dt)
    3. Ressonância: ω₀ = 1/√(LC), f₀ = ω₀/(2π)
    4. Amortecimento: ζ = R/(2√(L/C))
    5. Fator de qualidade: Q = ω₀L/R = 1/(2ζ)
    """
    
    def __init__(self, R=3.0, L=0.0005, C=100e-6):
        """
        Inicializa circuito RLC com parâmetros do carrinho.
        
        Args:
            R: Resistência (Ω) - motor
            L: Indutância (H) - bobina motor
            C: Capacitância (F) - capacitor filtro
        """
        self.R = R                          # 3Ω (motor)
        self.L = L                          # 0.5 mH
        self.C = C                          # 100 µF
        
        # Frequência natural e amortecimento
        self.omega_0 = 1 / np.sqrt(L * C)  # rad/s
        self.f_0 = self.omega_0 / (2 * np.pi)  # Hz
        
        # Fator de amortecimento (adimensional)
        self.zeta = R / (2 * np.sqrt(L / C))
        
        # Fator de qualidade
        self.Q = self.omega_0 * L / R
        
        # Frequência amortecida (se sub-amortecido)
        if self.zeta < 1:
            self.omega_d = self.omega_0 * np.sqrt(1 - self.zeta**2)
            self.f_d = self.omega_d / (2 * np.pi)
        else:
            self.omega_d = None
            self.f_d = None
    
    def tipo_resposta(self):
        """Classifica a resposta baseado em ζ"""
        if self.zeta < 1:
            return "Sub-amortecida (oscilatória)"
        elif self.zeta == 1:
            return "Criticamente amortecida"
        else:
            return "Sobre-amortecida (não-oscilatória)"
    
    def equacoes_diferenciais_transiente(self, y, t, V_entrada):
        """
        EDO para análise transiente do circuito RLC.
        
        y = [I, V_C]
        dI/dt = (V_entrada - I×R - V_C) / L
        dV_C/dt = I / C
        """
        I, V_C = y
        
        dI_dt = (V_entrada - I*self.R - V_C) / self.L
        dV_C_dt = I / self.C
        
        return [dI_dt, dV_C_dt]
    
    def simular_transiente(self, V_entrada=3.0, tempo_final=0.1, pontos=2000):
        """
        Simula resposta transiente do circuito RLC a degrau de voltagem.
        """
        t = np.linspace(0, tempo_final, pontos)
        y0 = [0, 0]  # I=0, V_C=0 inicialmente
        
        solucao = odeint(self.equacoes_diferenciais_transiente, y0, t, 
                        args=(V_entrada,))
        
        I = solucao[:, 0]
        V_C = solucao[:, 1]
        
        return t, I, V_C
    
    def resposta_em_frequencia(self, f_min=1, f_max=10000, pontos=1000):
        """
        Calcula resposta em frequência (magnitude e fase) do circuito RLC.
        
        Impedância: Z(ω) = R + j(ωL - 1/(ωC))
        """
        f = np.logspace(np.log10(f_min), np.log10(f_max), pontos)
        omega = 2 * np.pi * f
        
        # Impedância complexa
        Z_real = self.R
        Z_imag = omega * self.L - 1 / (omega * self.C)
        Z_mag = np.sqrt(Z_real**2 + Z_imag**2)
        
        # Admitância (1/Z) para corrente
        Y_mag = 1 / Z_mag
        
        # Fase
        fase = np.arctan2(Z_imag, Z_real) * 180 / np.pi
        
        return f, Z_mag, Y_mag, fase
    
    def imprimir_parametros(self):
        """Imprime parâmetros do circuito"""
        print("\n" + "="*70)
        print("PARÂMETROS DO CIRCUITO RLC")
        print("="*70)
        print(f"\nComponentes:")
        print(f"  R = {self.R:.1f}Ω (motor)")
        print(f"  L = {self.L*1e6:.1f}µH ({self.L*1e3:.1f}mH)")
        print(f"  C = {self.C*1e6:.1f}µF")
        print(f"\nFrequências:")
        print(f"  Frequência natural: f₀ = {self.f_0:.1f} Hz")
        print(f"  Período natural: T₀ = {1/self.f_0*1e3:.2f} ms")
        if self.f_d is not None:
            print(f"  Frequência amortecida: f_d = {self.f_d:.1f} Hz")
        print(f"\nAmortecimento:")
        print(f"  Fator de amortecimento: ζ = {self.zeta:.3f}")
        print(f"  Tipo de resposta: {self.tipo_resposta()}")
        print(f"  Fator de qualidade: Q = {self.Q:.2f}")
        print(f"\nInterpretação:")
        if self.zeta < 1:
            print(f"  - Circuito oscila com frequência f_d = {self.f_d:.1f} Hz")
            print(f"  - Amortecimento exponencial com τ = 1/(ζω₀) ≈ {1/(self.zeta*self.omega_0):.4f}s")
        print("="*70 + "\n")


# ============================================================================
# CASOS ESPECIAIS
# ============================================================================

def comparar_amortecimentos():
    """Compara respostas com diferentes fatores de amortecimento"""
    print("\nCOMPARAÇÃO DE AMORTECIMENTOS")
    print("-" * 70)
    
    casos = [
        ("Sub-amortecido", 0.3),
        ("Criticamente amortecido", 1.0),
        ("Sobre-amortecido", 2.0),
        ("Caso real (carrinho)", 3.0)
    ]
    
    for nome, R in casos:
        circ = CircuitoRLC(R=R, L=0.0005, C=100e-6)
        print(f"\n{nome}:")
        print(f"  ζ = {circ.zeta:.3f}, f₀ = {circ.f_0:.1f} Hz, Q = {circ.Q:.2f}")


# ============================================================================
# GRÁFICOS
# ============================================================================

def plotar_analise_rlc():
    """Plota análise completa do circuito RLC do carrinho"""
    
    # Parâmetros do carrinho (realistas)
    circ = CircuitoRLC(R=3.0, L=0.0005, C=100e-6)
    circ.imprimir_parametros()
    
    # Simular transiente
    t, I, V_C = circ.simular_transiente(V_entrada=3.0, tempo_final=0.1)
    
    # Resposta em frequência
    f, Z_mag, Y_mag, fase = circ.resposta_em_frequencia(f_min=1, f_max=50000)
    
    # Criar figura
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    fig.suptitle("Circuito RLC - Ressonância e Oscilações\nCarrinho RENLONG (R=3Ω, L=0.5mH, C=100µF)", 
                 fontsize=14, fontweight='bold')
    
    # 1. Resposta transiente - Corrente
    axes[0, 0].plot(t*1e3, I, 'b-', linewidth=2)
    axes[0, 0].set_xlabel('Tempo (ms)')
    axes[0, 0].set_ylabel('Corrente (A)')
    axes[0, 0].set_title(f'Resposta Transiente - Corrente\n(ζ={circ.zeta:.2f}, f₀={circ.f_0:.1f}Hz)')
    axes[0, 0].grid(True, alpha=0.3)
    axes[0, 0].axhline(y=1.0, color='r', linestyle='--', alpha=0.3)
    
    # 2. Resposta transiente - Tensão Capacitor
    axes[0, 1].plot(t*1e3, V_C, 'g-', linewidth=2)
    axes[0, 1].set_xlabel('Tempo (ms)')
    axes[0, 1].set_ylabel('Tensão Capacitor (V)')
    axes[0, 1].set_title(f'Resposta Transiente - Tensão Capacitor\n{circ.tipo_resposta()}')
    axes[0, 1].grid(True, alpha=0.3)
    axes[0, 1].axhline(y=3.0, color='r', linestyle='--', alpha=0.3)
    
    # 3. Impedância (log-log)
    axes[1, 0].loglog(f, Z_mag, 'r-', linewidth=2)
    axes[1, 0].axvline(x=circ.f_0, color='g', linestyle='--', linewidth=2, 
                        label=f'f₀ = {circ.f_0:.0f} Hz')
    axes[1, 0].set_xlabel('Frequência (Hz)')
    axes[1, 0].set_ylabel('Impedância |Z| (Ω)')
    axes[1, 0].set_title('Impedância vs Frequência')
    axes[1, 0].grid(True, which='both', alpha=0.3)
    axes[1, 0].legend()
    
    # 4. Fase da impedância
    axes[1, 1].semilogx(f, fase, 'b-', linewidth=2)
    axes[1, 1].axvline(x=circ.f_0, color='g', linestyle='--', linewidth=2)
    axes[1, 1].axhline(y=0, color='k', linestyle='-', linewidth=0.5)
    axes[1, 1].set_xlabel('Frequência (Hz)')
    axes[1, 1].set_ylabel('Fase (graus)')
    axes[1, 1].set_title(f'Fase vs Frequência (Q={circ.Q:.2f})')
    axes[1, 1].grid(True, which='both', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('./rlc_resonancia.png', dpi=300, bbox_inches='tight')
    print("✓ Gráfico salvo: rlc_resonancia.png")
    plt.close()


if __name__ == "__main__":
    comparar_amortecimentos()
    plotar_analise_rlc()
