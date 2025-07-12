import requests
from bs4 import BeautifulSoup
import gradio as gr
import re
import warnings
warnings.filterwarnings('ignore')

def fetch_html_content(input_text):
    """
    Fetch HTML content from a URL or process raw HTML input
    Returns the HTML content and source type for better user feedback
    """
    input_text = input_text.strip()
    
    # Check if input looks like HTML content
    if input_text.startswith('<') and '>' in input_text:
        return input_text, "raw_html"
    
    # Check if input looks like a URL
    if input_text.startswith(('http://', 'https://', 'www.')):
        try:
            # Add protocol if missing
            if input_text.startswith('www.'):
                input_text = 'https://' + input_text
            
            # Fetch the webpage
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(input_text, headers=headers, timeout=10)
            
            if response.status_code == 200:
                return response.text, "url"
            else:
                return None, f"HTTP Error {response.status_code}"
                
        except requests.exceptions.RequestException as e:
            return None, f"Request failed: {str(e)}"
    
    return None, "Invalid input format"

def check_alt_text(soup, base_url=""):
    """
    Comprehensive check for image alt text accessibility
    Returns detailed issues and suggestions for improvement
    """
    issues = []
    suggestions = []
    
    # Find all image elements
    images = soup.find_all('img')
    
    if not images:
        return [], ["Consider adding relevant images with proper alt text to enhance content."]
    
    for i, img in enumerate(images, 1):
        alt = img.get('alt')
        src = img.get('src', 'Unknown source')
        
        # Check for missing alt attribute
        if alt is None:
            issues.append({
                'type': 'Missing Alt Attribute',
                'element': f'Image {i}',
                'description': f'Image with src="{src}" has no alt attribute',
                'severity': 'High',
                'wcag': 'WCAG 2.1 Level A - 1.1.1'
            })
        
        # Check for empty alt text (which is valid for decorative images)
        elif alt.strip() == '':
            issues.append({
                'type': 'Empty Alt Text',
                'element': f'Image {i}',
                'description': f'Image with src="{src}" has empty alt text (okay if decorative)',
                'severity': 'Medium',
                'wcag': 'WCAG 2.1 Level A - 1.1.1'
            })
        
        # Check for poor alt text practices
        elif alt.strip().lower() in ['image', 'picture', 'photo', 'img']:
            issues.append({
                'type': 'Generic Alt Text',
                'element': f'Image {i}',
                'description': f'Alt text "{alt}" is too generic and not descriptive',
                'severity': 'Medium',
                'wcag': 'WCAG 2.1 Level A - 1.1.1'
            })
    
    # Generate suggestions based on issues found
    if issues:
        suggestions.extend([
            "Write descriptive alt text that conveys the meaning and context of images",
            "Use empty alt='' for purely decorative images",
            "Avoid generic terms like 'image', 'picture', or 'photo'",
            "Keep alt text concise but meaningful (aim for 125 characters or less)"
        ])
    
    return issues, suggestions

def check_font_sizes(soup):
    """
    Analyze font sizes and readability issues in the HTML content
    """
    issues = []
    suggestions = []
    
    # Check inline styles for font-size
    elements_with_styles = soup.find_all(style=True)
    small_fonts_found = False
    
    for i, element in enumerate(elements_with_styles, 1):
        style = element.get('style', '')
        
        # Look for font-size declarations
        font_size_match = re.search(r'font-size:\s*(\d+(?:\.\d+)?)(px|pt|em|rem|%)', style, re.IGNORECASE)
        
        if font_size_match:
            size_value = float(font_size_match.group(1))
            unit = font_size_match.group(2).lower()
            
            # Convert to approximate pixel values for comparison
            if unit == 'px':
                pixel_size = size_value
            elif unit == 'pt':
                pixel_size = size_value * 1.33  # Rough conversion
            elif unit in ['em', 'rem']:
                pixel_size = size_value * 16  # Assuming 16px base
            elif unit == '%':
                pixel_size = (size_value / 100) * 16  # Assuming 16px base
            else:
                continue
            
            # Flag very small fonts (less than 12px equivalent)
            if pixel_size < 12:
                issues.append({
                    'type': 'Small Font Size',
                    'element': f'Element {i} ({element.name})',
                    'description': f'Font size {size_value}{unit} (≈{pixel_size:.1f}px) may be too small for readability',
                    'severity': 'Medium',
                    'wcag': 'WCAG 2.1 Level AA - 1.4.4'
                })
                small_fonts_found = True
    
    # Check for potential readability issues with text content
    text_elements = soup.find_all(['p', 'div', 'span', 'li', 'td', 'th'])
    long_paragraphs = 0
    
    for element in text_elements:
        text = element.get_text(strip=True)
        if len(text) > 500:  # Very long text blocks
            long_paragraphs += 1
    
    if long_paragraphs > 0:
        issues.append({
            'type': 'Long Text Blocks',
            'element': f'{long_paragraphs} elements',
            'description': f'Found {long_paragraphs} very long text blocks that may hurt readability',
            'severity': 'Low',
            'wcag': 'WCAG 2.1 Level AAA - 2.4.8'
        })
    
    # Generate suggestions
    if small_fonts_found:
        suggestions.extend([
            "Use minimum 12px font size for body text (14px+ recommended)",
            "Ensure text can be zoomed to 200% without loss of functionality",
            "Test readability on different devices and screen sizes"
        ])
    
    if long_paragraphs > 0:
        suggestions.append("Break up long text blocks with headings, bullet points, or shorter paragraphs")
    
    return issues, suggestions

def check_color_contrast(soup):
    """
    Analyze color contrast issues in the HTML content
    This is a simplified heuristic check - full WCAG compliance requires more complex calculations
    """
    issues = []
    suggestions = []
    
    # Check elements with inline color styles
    elements_with_styles = soup.find_all(style=True)
    contrast_issues_found = False
    
    for i, element in enumerate(elements_with_styles, 1):
        style = element.get('style', '')
        
        # Extract color and background-color
        color_match = re.search(r'color:\s*([^;]+)', style, re.IGNORECASE)
        bg_match = re.search(r'background-color:\s*([^;]+)', style, re.IGNORECASE)
        
        if color_match and bg_match:
            text_color = color_match.group(1).strip()
            bg_color = bg_match.group(1).strip()
            
            # Simplified contrast check using color name heuristics
            light_colors = ['white', '#fff', '#ffffff', '#f0f0f0', '#e0e0e0', 
                          'yellow', 'lightyellow', 'lightgray', 'lightgrey', 'beige']
            dark_colors = ['black', '#000', '#000000', '#333', '#666', 
                         'navy', 'darkblue', 'darkgreen', 'darkred', 'purple']
            
            text_is_light = any(light in text_color.lower() for light in light_colors)
            text_is_dark = any(dark in text_color.lower() for dark in dark_colors)
            bg_is_light = any(light in bg_color.lower() for light in light_colors)
            bg_is_dark = any(dark in bg_color.lower() for dark in dark_colors)
            
            # Flag potential contrast issues
            if (text_is_light and bg_is_light) or (text_is_dark and bg_is_dark):
                issues.append({
                    'type': 'Poor Color Contrast',
                    'element': f'Element {i} ({element.name})',
                    'description': f'Text color "{text_color}" on background "{bg_color}" may have insufficient contrast',
                    'severity': 'High',
                    'wcag': 'WCAG 2.1 Level AA - 1.4.3'
                })
                contrast_issues_found = True
    
    # Check for color-only information conveyance
    elements_with_color = soup.find_all(lambda tag: tag.get('style') and 'color:' in tag.get('style', ''))
    if len(elements_with_color) > 5:  # Arbitrary threshold
        issues.append({
            'type': 'Color Dependency',
            'element': f'{len(elements_with_color)} elements',
            'description': 'Heavy reliance on color - ensure information is also conveyed through other means',
            'severity': 'Medium',
            'wcag': 'WCAG 2.1 Level A - 1.4.1'
        })
    
    # Generate suggestions
    if contrast_issues_found:
        suggestions.extend([
            "Ensure text has at least 4.5:1 contrast ratio with background (7:1 for AAA compliance)",
            "Test colors using online contrast checkers",
            "Avoid using similar shades for text and background"
        ])
    
    if len(elements_with_color) > 5:
        suggestions.append("Don't rely solely on color to convey information - use icons, text, or patterns too")
    
    return issues, suggestions

def analyze_accessibility(input_text):
    """
    Main function to analyze HTML content for accessibility issues
    """
    if not input_text.strip():
        return "Please provide a URL or HTML content to analyze.", "Ready to analyze...", 0
    
    # Fetch HTML content
    html_content, source_type = fetch_html_content(input_text)
    
    if html_content is None:
        return f"Error: {source_type}", "Error occurred", 0
    
    # Parse HTML
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
    except Exception as e:
        return f"Error parsing HTML: {str(e)}", "Parsing error", 0
    
    # Perform accessibility checks
    alt_issues, alt_suggestions = check_alt_text(soup)
    font_issues, font_suggestions = check_font_sizes(soup)
    color_issues, color_suggestions = check_color_contrast(soup)
    
    # Combine all issues
    all_issues = alt_issues + font_issues + color_issues
    all_suggestions = list(set(alt_suggestions + font_suggestions + color_suggestions))  # Remove duplicates
    
    # Generate report
    if not all_issues:
        report = "🎉 **Great news!** No major accessibility issues detected.\n\n"
        report += "However, consider these general best practices:\n"
        for suggestion in all_suggestions[:3]:  # Show top 3 general suggestions
            report += f"• {suggestion}\n"
        return report, "✅ Accessibility check completed successfully!", len(all_issues)
    
    # Create detailed report
    report = f"## 🔍 Accessibility Analysis Report\n\n"
    report += f"**Issues Found:** {len(all_issues)}\n"
    report += f"**Source:** {source_type.replace('_', ' ').title()}\n\n"
    
    # Group issues by severity
    high_issues = [issue for issue in all_issues if issue['severity'] == 'High']
    medium_issues = [issue for issue in all_issues if issue['severity'] == 'Medium']
    low_issues = [issue for issue in all_issues if issue['severity'] == 'Low']
    
    # Report high priority issues first
    if high_issues:
        report += "### 🚨 High Priority Issues\n"
        for issue in high_issues:
            report += f"**{issue['type']}** - {issue['element']}\n"
            report += f"• {issue['description']}\n"
            report += f"• Standard: {issue['wcag']}\n\n"
    
    if medium_issues:
        report += "### ⚠️ Medium Priority Issues\n"
        for issue in medium_issues:
            report += f"**{issue['type']}** - {issue['element']}\n"
            report += f"• {issue['description']}\n"
            report += f"• Standard: {issue['wcag']}\n\n"
    
    if low_issues:
        report += "### 💡 Low Priority Issues\n"
        for issue in low_issues:
            report += f"**{issue['type']}** - {issue['element']}\n"
            report += f"• {issue['description']}\n"
            report += f"• Standard: {issue['wcag']}\n\n"
    
    # Add suggestions
    if all_suggestions:
        report += "## 🛠️ Recommended Actions\n\n"
        for i, suggestion in enumerate(all_suggestions, 1):
            report += f"{i}. {suggestion}\n"
    
    return report, f"Analysis completed! Found {len(all_issues)} accessibility issues.", len(all_issues)

def create_accessibility_interface():
    """
    Create the Gradio interface for the accessibility checker
    """
    
    # Custom CSS for better styling
    css = """
    .gradio-container {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    .report-box {
        background-color: black;
        border-radius: 8px;
        padding: 15px;
        border: 1px solid #dee2e6;
    }
    """
    
    with gr.Blocks(title="🌐 Accessibility Checker", theme=gr.themes.Soft(), css=css) as demo:
        
        gr.Markdown("""
        # 🌐 Personalized Accessibility Checker
        
        **Make the web more inclusive!** This tool analyzes web pages and HTML content for accessibility issues, 
        helping you create content that's usable by everyone, including people with disabilities.
        
        ### What We Check:
        - 🖼️ **Alt text** for images (screen reader compatibility)
        - 📝 **Font sizes** and readability
        - 🎨 **Color contrast** between text and backgrounds
        - 📋 **WCAG compliance** with specific guidelines
        
        ### How to Use:
        1. Enter a website URL (e.g., `https://example.com`) **OR** paste HTML content
        2. Click "Analyze Accessibility" 
        3. Review the detailed report and suggestions
        """)
        
        with gr.Row():
            with gr.Column(scale=2):
                input_box = gr.Textbox(
                    label="🌐 Website URL or HTML Content",
                    placeholder="Enter URL (https://example.com) or paste HTML content here...",
                    lines=3,
                    max_lines=10
                )
                
                analyze_btn = gr.Button(
                    "🔍 Analyze Accessibility", 
                    variant="primary",
                    size="lg"
                )
                
            with gr.Column(scale=1):
                status_box = gr.Textbox(
                    label="📊 Status",
                    value="Ready to analyze...",
                    interactive=False,
                    lines=2
                )
                
                issue_count = gr.Number(
                    label="Issues Found",
                    value=0,
                    interactive=False
                )
        
        # Results area
        report_output = gr.Markdown(
            label="📋 Accessibility Report",
            value="Your detailed accessibility analysis will appear here...",
            elem_classes=["report-box"]
        )
        
        # Example URLs section
        gr.Markdown("### 🧪 Try These Example URLs:")
        
        example_urls = [
            "https://www.w3.org/WAI/",  # Good accessibility
            "https://example.com",      # Simple site
        ]
        
        with gr.Row():
            for url in example_urls:
                gr.Button(f"Test: {url.split('//')[1]}", size="sm").click(
                    lambda u=url: u,
                    outputs=input_box
                )
        
        # Example HTML section
        gr.Markdown("### 📝 Or Try This Example HTML:")
        
        example_html = '''<html>
<body>
    <h1 style="color: yellow; background-color: white;">Welcome</h1>
    <img src="logo.jpg">
    <p style="font-size: 8px;">This text is too small</p>
    <div style="color: lightgray; background-color: white;">Poor contrast text</div>
</body>
</html>'''
        
        gr.Button("📄 Load Example HTML", size="sm").click(
            lambda: example_html,
            outputs=input_box
        )
        
        # Set up event handlers
        analyze_btn.click(
            fn=analyze_accessibility,
            inputs=[input_box],
            outputs=[report_output, status_box, issue_count]
        )
        
        # Real-time analysis (optional)
        input_box.change(
            fn=lambda text: ("Ready to analyze..." if text.strip() else "Enter URL or HTML content"),
            inputs=[input_box],
            outputs=[status_box]
        )
        
        # Footer with resources
        gr.Markdown("""
        ---
        ### 📚 Accessibility Resources:
        - **WCAG Guidelines**: Web Content Accessibility Guidelines 2.1
        - **Color Contrast**: Aim for 4.5:1 ratio (normal text) or 3:1 (large text)
        - **Alt Text**: Describe the content and function of images
        - **Font Size**: Minimum 12px, recommended 14px+ for body text
        
        *This tool provides basic accessibility checking. For comprehensive testing, use specialized tools and manual testing.*
        """)
    
    return demo

# Create and launch the interface
if __name__ == "__main__":
    demo = create_accessibility_interface()
    demo.launch()
