from __future__ import annotations
import os
import tempfile
import matplotlib
matplotlib.use("Agg")  # Backend sin GUI para servidores
import matplotlib.pyplot as plt
import cafi_agent.storage as storage


def generate_pie_chart() -> str | None:
    """Genera un gráfico de torta con la distribución de gastos por categoría."""
    data = storage.get_periodo_data()
    gastos_cat = data.get("gastos_por_categoria", {})

    # Filtrar solo categorías con monto > 0
    labels = []
    sizes = []
    for cat, monto in gastos_cat.items():
        if monto and float(monto) > 0:
            labels.append(cat)
            sizes.append(float(monto))

    if not sizes:
        return None

    # Paleta de colores moderna
    colors = [
        "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4",
        "#FFEAA7", "#DDA0DD", "#98D8C8", "#F7DC6F",
        "#BB8FCE", "#85C1E9", "#F0B27A"
    ]

    fig, ax = plt.subplots(figsize=(8, 6))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#1a1a2e")

    wedges, texts, autotexts = ax.pie(
        sizes,
        labels=labels,
        autopct="%1.1f%%",
        colors=colors[:len(labels)],
        startangle=140,
        textprops={"color": "white", "fontsize": 10},
        pctdistance=0.80,
        wedgeprops={"edgecolor": "#1a1a2e", "linewidth": 2}
    )

    for t in autotexts:
        t.set_fontweight("bold")
        t.set_fontsize(9)

    total = sum(sizes)
    ax.set_title(
        f"Distribucion de Gastos\nTotal: ${total:,.0f} COP",
        color="white", fontsize=14, fontweight="bold", pad=20
    )

    path = os.path.join(tempfile.gettempdir(), "cafi_pie.png")
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def generate_bar_chart() -> str | None:
    """Genera un gráfico de barras comparando Ingresos, Gastos y Balance."""
    data = storage.get_periodo_data()
    if not data:
        return None

    ingresos = float(data.get("ingresos_totales", 0))
    gastos = float(data.get("gastos_totales", 0))
    balance = float(data.get("balance", 0))

    if ingresos == 0 and gastos == 0:
        return None

    categories = ["Ingresos", "Gastos", "Balance"]
    values = [ingresos, gastos, balance]
    colors = ["#2ecc71", "#e74c3c", "#3498db" if balance >= 0 else "#e67e22"]

    fig, ax = plt.subplots(figsize=(8, 5))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#16213e")

    bars = ax.bar(categories, values, color=colors, width=0.5, edgecolor="#1a1a2e", linewidth=2)

    # Etiquetas de valor sobre cada barra
    for bar, val in zip(bars, values):
        y_pos = bar.get_height() if val >= 0 else bar.get_height() - abs(val) * 0.05
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            y_pos + max(values) * 0.02,
            f"${val:,.0f}",
            ha="center", va="bottom",
            color="white", fontweight="bold", fontsize=11
        )

    ax.set_title(
        "Resumen Financiero del Periodo",
        color="white", fontsize=14, fontweight="bold", pad=15
    )
    ax.tick_params(colors="white")
    ax.spines["bottom"].set_color("white")
    ax.spines["left"].set_color("white")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    for label in ax.get_xticklabels():
        label.set_color("white")
        label.set_fontsize(12)
    for label in ax.get_yticklabels():
        label.set_color("white")

    ax.axhline(y=0, color="white", linewidth=0.5, alpha=0.3)

    path = os.path.join(tempfile.gettempdir(), "cafi_bar.png")
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return path
