import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import matplotlib.colors as mcolors

def create_ironbow_cmap():
    """Recreates the custom Ironbow palette defined in the project."""
    # Colors: Deep Purple, Magenta, Orange, White/Yellow
    colors = ["#180826", "#A91C68", "#F28218", "#FFFFA0"]
    return mcolors.LinearSegmentedColormap.from_list("ironbow_custom", colors)

def generate_banner():
    # Setup Figure
    dpi = 100
    width_px, height_px = 1200, 400
    fig = plt.figure(figsize=(width_px/dpi, height_px/dpi), dpi=dpi)
    
    # Background (Dark UI Grey)
    fig.patch.set_facecolor('#1E1E1E')
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()

    # 1. Generate Synthetic Thermal Data (Blobs)
    x = np.linspace(-3, 3, 300)
    y = np.linspace(-3, 3, 300)
    X, Y = np.meshgrid(x, y)
    
    # Create "Hot spots"
    Z1 = np.exp(-(X**2 + Y**2))
    Z2 = np.exp(-((X - 1)**2 + (Y - 1)**2)) * 0.8
    Z3 = np.exp(-((X + 1.5)**2 + (Y + 0.5)**2) / 0.5) * 0.6
    Z = Z1 + Z2 + Z3
    
    # 2. Draw Split View Background
    # Right side: Thermal
    ax.imshow(Z, cmap=create_ironbow_cmap(), extent=[600, 1200, 0, 400], alpha=0.9)
    
    # Left side: "RGB" (Simulated by Grayscale + Edge styling)
    # We use the same Z data but render it as a "structural" wireframe look
    ax.imshow(Z, cmap='gray', extent=[0, 600, 0, 400], alpha=0.3)
    
    # Add grid lines to left side to look like "Analysis"
    for i in range(0, 600, 50):
        rect = patches.Rectangle((i, 0), 1, 400, linewidth=0, facecolor='#2196F3', alpha=0.1)
        ax.add_patch(rect)

    # 3. Add Diagonal Split Line
    split_x = [600, 550] 
    split_y = [0, 400]
    plt.plot([600, 600], [0, 400], color='white', linewidth=2)

    # 4. Text Overlay
    # Main Title
    plt.text(50, 250, "THERMAL INSPECTION", color='white', fontsize=38, fontname='Arial', fontweight='bold')
    plt.text(50, 200, "FUSION TOOL", color='#F28218', fontsize=38, fontname='Arial', fontweight='bold')
    
    # Subtitle / Features
    features = "• Radiometric Analysis  • 9 Fusion Modes  • FLIR Boson Support"
    plt.text(50, 140, features, color='#CCCCCC', fontsize=14, fontname='Arial')

    # 5. UI Elements Simulation (The "Focus Box")
    # Draw a bounding box around a "hot spot" on the right
    rect = patches.Rectangle((850, 200), 100, 100, linewidth=2, edgecolor='#FFFFA0', facecolor='none')
    ax.add_patch(rect)
    plt.text(855, 310, "MAX: 85.4°C", color='#FFFFA0', fontsize=10, fontweight='bold')

    # Save
    plt.savefig('banner_hero.png', facecolor=fig.get_facecolor())
    print("Banner generated: banner_hero.png")

if __name__ == "__main__":
    generate_banner()