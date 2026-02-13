import os

def generate_sample_chart():
    svg_content = """<svg width="400" height="300" xmlns="http://www.w3.org/2000/svg">
  <rect width="100%" height="100%" fill="#f9f9f9"/>
  <line x1="50" y1="250" x2="350" y2="250" stroke="#333" stroke-width="2"/>
  <line x1="50" y1="50" x2="50" y2="250" stroke="#333" stroke-width="2"/>
  
  <!-- Bar 1 -->
  <rect x="70" y="100" width="40" height="150" fill="#4a90e2"/>
  <text x="70" y="270" font-family="Arial" font-size="12">Q1</text>
  
  <!-- Bar 2 -->
  <rect x="140" y="150" width="40" height="100" fill="#50e3c2"/>
  <text x="140" y="270" font-family="Arial" font-size="12">Q2</text>
  
  <!-- Bar 3 -->
  <rect x="210" y="80" width="40" height="170" fill="#f5a623"/>
  <text x="210" y="270" font-family="Arial" font-size="12">Q3</text>
  
  <!-- Bar 4 -->
  <rect x="280" y="120" width="40" height="130" fill="#d0021b"/>
  <text x="280" y="270" font-family="Arial" font-size="12">Q4</text>
  
  <text x="200" y="30" font-family="Arial" font-size="16" text-anchor="middle" font-weight="bold">Sample Growth Chart</text>
</svg>"""
    
    output_dir = os.path.join(os.path.dirname(__file__), "generated")
    os.makedirs(output_dir, exist_ok=True)
    
    with open(os.path.join(output_dir, "sample-chart.svg"), "w") as f:
        f.write(svg_content)
    print(f"Generated sample chart in {output_dir}")

if __name__ == "__main__":
    generate_sample_chart()
