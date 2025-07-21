
import os

def get_structure(start_path='.', indent=''):
    lines = []
    for item in sorted(os.listdir(start_path)):
        item_path = os.path.join(start_path, item)
        if os.path.isdir(item_path):
            lines.append(f"{indent}📁 {item}")
            lines.extend(get_structure(item_path, indent + '    '))
        else:
            lines.append(f"{indent}📄 {item}")
    return lines

if __name__ == '__main__':
    root = r'C:\Users\localadmin\Desktop\UAL-AutoAnalyzer'  # Change this to your project directory if needed
    output_file = 'project_structure.txt'

    structure_lines = ["🗂️ Project Structure:\n"] + get_structure(root)
    
    # Print to console
    for line in structure_lines:
        print(line)
    
    # Save to text file
    with open(output_file, 'w', encoding='utf-8') as f:
        for line in structure_lines:
            f.write(line + '\n')

    print(f"\n✅ Project structure saved to: {output_file}")
