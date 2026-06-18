"""
ANÁLISE DE FREQUÊNCIA COM FFT
Fenômenos Elétricos, Magnéticos e Oscilatórios

Autor: Projeto Engenharias 2026-1
Data: Maio 2026

Este módulo realiza análise de Fourier (FFT) para:
- Decompor sinal de corrente em harmônicas
- Identificar frequências dominantes
- Detectar componentes DC, fundamental e harmônicas
- Aplicação: análise de ripple em carrinho RC

Transformada de Fourier Discreta (DFT):
X[k] = Σ(n=0 a N-1) x[n] × e^(-j2πkn/N)

Interpretação:
- Magnitude: amplitude de cada frequência
- Fase: relação de tempo entre componentes
- Harmônicos: múltiplos inteiros da frequência fundamental
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.fft import fft, fftfreq
from scipy.signal import windows

# ============================================================================
# GERAÇÃO DE SINAIS E FFT
# ============================================================================

class AnalisadorFrequencia:
    """
    Analisa conteúdo em frequência de sinais.
    Típicos em sistemas de potência e eletrônica: corrente, tensão, etc.
    """
    
    def __init__(self, frequencia_amostragem=10000):
        """
        Inicializa analisador.
        
        Args:
            frequencia_amostragem: Hz (padrão 10 kHz para capturar até ~5 kHz)
        """
        self.fs = frequencia_amostragem
        self.periodo_amostragem = 1 / self.fs
    
    def gerar_sinal_corrente_motor(self, tempo_total=0.1, 
                                    freq_fundamental=50, 
                                    harmonica_2=False, harmonica_3=False):
        """
        Gera sinal de corrente com componentes DC, fundamental e harmônicas.
        
        Modelo realista para corrente de motor:
        i(t) = I_DC + I_1×sin(2πf₁t) + I_3×sin(2πf₃t) + I_5×sin(2πf₅t) + ruído
        
        Args:
            tempo_total: duração do sinal (s)
            freq_fundamental: frequência da componente principal (Hz)
            harmonica_2, harmonica_3: ativar 3ª e 5ª harmônicas
        """
        # Vetor de tempo
        t = np.arange(0, tempo_total, self.periodo_amostragem)
        N = len(t)
        
        # Sinal: DC + fundamental + harmônicas
        I_DC = 1.0  # Componente DC (1A)
        I_1 = 0.9   # Fundamental (fundamental)
        
        i_t = I_DC + I_1 * np.sin(2*np.pi*freq_fundamental*t)
        
        if harmonica_2:
            I_3 = 0.3  # 3ª harmônica (35% da fundamental)
            i_t += I_3 * np.sin(2*np.pi*3*freq_fundamental*t + np.pi/4)
        
        if harmonica_3:
            I_5 = 0.15  # 5ª harmônica (15% da fundamental)
            i_t += I_5 * np.sin(2*np.pi*5*freq_fundamental*t + np.pi/3)
        
        # Adicionar ruído (±5% da fundamental)
        ruido = 0.05 * I_1 * np.random.randn(N)
        i_t += ruido
        
        return t, i_t
    
    def calcular_fft(self, sinal, tempo):
        """
        Calcula FFT do sinal.
        
        Retorna:
            freqs: frequências (Hz)
            X: magnitude do espectro
            fase: fase das componentes
        """
        N = len(sinal)
        
        # Aplicar janela de Hanning para reduzir vazamento espectral
        janela = windows.hann(N)
        sinal_janelado = sinal * janela
        
        # FFT
        X = fft(sinal_janelado)
        freqs = fftfreq(N, self.periodo_amostragem)
        
        # Magnitude (bilateral → unilateral, × 2)
        magnitude = 2 * np.abs(X) / N
        
        # Fase
        fase = np.angle(X)
        
        # Tomar apenas frequências positivas
        idx_positivo = freqs >= 0
        freqs = freqs[idx_positivo]
        magnitude = magnitude[idx_positivo]
        fase = fase[idx_positivo]
        
        return freqs, magnitude, fase
    
    def encontrar_picos(self, freqs, magnitude, num_picos=5, threshold=0.1):
        """
        Encontra frequências dominantes (picos) no espectro.
        """
        # Normalizar
        mag_norm = magnitude / np.max(magnitude)
        
        # Encontrar picos acima de threshold
        picos_idx = np.where(mag_norm > threshold)[0]
        
        # Ordenar por magnitude
        picos_idx = picos_idx[np.argsort(mag_norm[picos_idx])[::-1]]
        picos_idx = picos_idx[:num_picos]
        
        picos_freq = freqs[picos_idx]
        picos_mag = mag_norm[picos_idx]
        
        return picos_freq, picos_mag, picos_idx
    
    def calcular_thd(self, freqs, magnitude, freq_fundamental):
        """
        Calcula THD (Total Harmonic Distortion).
        
        THD = √(Σ(I_n² para n=2,∞)) / I_1 × 100%
        """
        # Encontrar índice da fundamental
        idx_fundamental = np.argmin(np.abs(freqs - freq_fundamental))
        I_1 = magnitude[idx_fundamental]
        
        if I_1 < 1e-6:
            return 0
        
        # Somar quadrado das harmônicas (acima de 2×fundamental)
        idx_harmonicas = np.where((freqs > freq_fundamental * 1.5) & 
                                  (freqs < freq_fundamental * 50))[0]
        
        soma_harmonicas_sq = np.sum(magnitude[idx_harmonicas]**2)
        
        thd = (np.sqrt(soma_harmonicas_sq) / I_1) * 100
        return thd
    
    def imprimir_analise(self, freqs, magnitude, freq_fundamental):
        """Imprime análise de frequência"""
        picos_f, picos_m, _ = self.encontrar_picos(freqs, magnitude, num_picos=10)
        thd = self.calcular_thd(freqs, magnitude, freq_fundamental)
        
        print("\n" + "="*70)
        print("ANÁLISE DE FREQUÊNCIA - FFT")
        print("="*70)
        print(f"\nFrequência de amostragem: {self.fs} Hz")
        print(f"Frequência fundamental esperada: {freq_fundamental} Hz")
        print(f"\nComponentes principais (top 10):")
        print(f"{'Frequência (Hz)':<20} {'Magnitude (A)':<20} {'% Fundamental':<20}")
        print("-" * 70)
        
        for f, m in zip(picos_f, picos_m):
            pct = (m / np.max(magnitude)) * 100
            print(f"{f:>15.1f}     {m:>15.3f}     {pct:>15.1f}%")
        
        print(f"\nTHD (Total Harmonic Distortion): {thd:.2f}%")
        print("="*70 + "\n")


# ============================================================================
# GRÁFICOS
# ============================================================================

def plotar_fft_corrente():
    """Plota análise FFT da corrente do motor"""
    
    # Criar analisador
    analisador = AnalisadorFrequencia(frequencia_amostragem=10000)
    
    # Gerar sinais: com e sem harmônicas
    print("\nGerando sinais de corrente...")
    
    # Caso 1: Apenas fundamental (ideal)
    t1, i1 = analisador.gerar_sinal_corrente_motor(tempo_total=0.2, 
                                                     freq_fundamental=50,
                                                     harmonica_2=False, 
                                                     harmonica_3=False)
    
    # Caso 2: Com harmônicas (realista)
    t2, i2 = analisador.gerar_sinal_corrente_motor(tempo_total=0.2, 
                                                     freq_fundamental=50,
                                                     harmonica_2=True, 
                                                     harmonica_3=True)
    
    # Calcular FFT
    freqs1, mag1, fase1 = analisador.calcular_fft(i1, t1)
    freqs2, mag2, fase2 = analisador.calcular_fft(i2, t2)
    
    # Imprimir análise
    print("\nCaso 1: Sinal ideal (apenas fundamental)")
    analisador.imprimir_analise(freqs1, mag1, 50)
    
    print("\nCaso 2: Sinal realista (com harmônicas)")
    analisador.imprimir_analise(freqs2, mag2, 50)
    
    # Criar figura
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    fig.suptitle("Análise de Frequência (FFT) - Corrente do Motor\nf_fundamental = 50 Hz", 
                 fontsize=14, fontweight='bold')
    
    # 1. Sinal ideal no tempo
    axes[0, 0].plot(t1*1e3, i1, 'b-', linewidth=1, alpha=0.7)
    axes[0, 0].set_xlabel('Tempo (ms)')
    axes[0, 0].set_ylabel('Corrente (A)')
    axes[0, 0].set_title('Sinal Ideal - Domínio do Tempo')
    axes[0, 0].grid(True, alpha=0.3)
    axes[0, 0].set_xlim([0, 100])
    
    # 2. Espectro ideal
    axes[0, 1].stem(freqs1, mag1, basefmt=' ')
    axes[0, 1].set_xlabel('Frequência (Hz)')
    axes[0, 1].set_ylabel('Magnitude (A)')
    axes[0, 1].set_title('Sinal Ideal - Espectro FFT')
    axes[0, 1].set_xlim([0, 500])
    axes[0, 1].set_ylim([0, 1.5])
    axes[0, 1].grid(True, alpha=0.3)
    
    # 3. Sinal realista no tempo
    axes[1, 0].plot(t2*1e3, i2, 'r-', linewidth=1, alpha=0.7)
    axes[1, 0].set_xlabel('Tempo (ms)')
    axes[1, 0].set_ylabel('Corrente (A)')
    axes[1, 0].set_title('Sinal Realista (com harmônicas) - Domínio do Tempo')
    axes[1, 0].grid(True, alpha=0.3)
    axes[1, 0].set_xlim([0, 100])
    
    # 4. Espectro realista
    axes[1, 1].stem(freqs2, mag2, basefmt=' ')
    axes[1, 1].set_xlabel('Frequência (Hz)')
    axes[1, 1].set_ylabel('Magnitude (A)')
    axes[1, 1].set_title('Sinal Realista - Espectro FFT (com 3ª e 5ª harmônicas)')
    axes[1, 1].set_xlim([0, 500])
    axes[1, 1].set_ylim([0, 1.5])
    axes[1, 1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('./fft_analise_frequencia.png', dpi=300, bbox_inches='tight')
    print("\n✓ Gráfico salvo: fft_analise_frequencia.png")
    plt.close()


if __name__ == "__main__":
    plotar_fft_corrente()
