from flask import Flask, render_template, request, jsonify
import pandas as pd
import os
from werkzeug.utils import secure_filename
import tempfile

app = Flask(__name__)

# Configure file uploads
ALLOWED_EXTENSIONS = {'csv'}
UPLOAD_FOLDER = tempfile.gettempdir()  # Use system temp directory
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

def allowed_file(filename):
    """Check if the uploaded file is a CSV file."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def home():
    """Display the main clock page."""
    return render_template('index.html')

@app.route('/csv-analyzer')
def csv_analyzer():
    """Display the CSV analyzer page."""
    return render_template('csv_analyzer.html')

@app.route('/upload-csv', methods=['POST'])
def upload_csv():
    """
    Handle CSV file upload and return statistical summary.
    
    Expected POST data:
    - file: CSV file to upload
    
    Returns JSON with:
    - success: boolean indicating success/failure
    - stats: dictionary with statistical summary (if successful)
    - error: error message (if failed)
    """
    # Check if file is in request
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    # Check if file is empty
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400
    
    # Check if file is allowed
    if not allowed_file(file.filename):
        return jsonify({'success': False, 'error': 'Only CSV files are allowed'}), 400
    
    try:
        # Try to read the CSV file with different encodings
        # Start with UTF-8, then try UTF-16, UTF-8-sig, latin-1, and iso-8859-1
        encodings = ['utf-8', 'utf-16', 'utf-8-sig', 'latin-1', 'iso-8859-1', 'cp1252']
        df = None
        last_error = None
        
        for encoding in encodings:
            try:
                file.seek(0)  # Reset file pointer to beginning
                # Try to read with different delimiters and error handling
                delimiters = [',', ';', '\t', '|']
                
                for delimiter in delimiters:
                    try:
                        file.seek(0)
                        df = pd.read_csv(
                            file,
                            encoding=encoding,
                            delimiter=delimiter,
                            on_bad_lines='skip',  # Skip problematic rows
                            engine='python',  # More lenient parser
                            dtype=str  # Read all as strings initially to preserve data
                        )
                        
                        # If we got here, skip remaining encodings/delimiters
                        if not df.empty:
                            break
                    except (UnicodeDecodeError, UnicodeError):
                        continue
                    except Exception:
                        continue
                
                if df is not None and not df.empty:
                    # Convert numeric columns to appropriate types
                    for col in df.columns:
                        try:
                            df[col] = pd.to_numeric(df[col], errors='ignore')
                        except:
                            pass
                    break  # Successfully read, exit encoding loop
                    
            except (UnicodeDecodeError, UnicodeError) as e:
                last_error = e
                continue  # Try next encoding
        
        if df is None or df.empty:
            raise ValueError(f"Could not decode CSV file with any supported encoding. Last error: {last_error}")
        
        # Check if DataFrame is empty
        if df.empty:
            return jsonify({'success': False, 'error': 'CSV file is empty'}), 400
        
        # Generate statistical summary
        stats = {}
        
        # Overall statistics
        stats['total_rows'] = int(df.shape[0])
        stats['total_columns'] = int(df.shape[1])
        stats['column_names'] = df.columns.tolist()
        
        # Per-column statistics
        column_stats = {}
        for col in df.columns:
            col_data = {}
            col_data['dtype'] = str(df[col].dtype)
            col_data['non_null_count'] = int(df[col].count())
            col_data['null_count'] = int(df[col].isna().sum())
            col_data['null_percentage'] = round(
                (df[col].isna().sum() / len(df)) * 100, 2
            )
            col_data['unique_values'] = int(df[col].nunique())
            
            # Numeric statistics (only for numeric columns)
            if pd.api.types.is_numeric_dtype(df[col]):
                col_data['min'] = float(df[col].min())
                col_data['max'] = float(df[col].max())
                col_data['mean'] = round(float(df[col].mean()), 4)
                col_data['median'] = round(float(df[col].median()), 4)
                col_data['std_dev'] = round(float(df[col].std()), 4)
                col_data['25_percentile'] = round(float(df[col].quantile(0.25)), 4)
                col_data['75_percentile'] = round(float(df[col].quantile(0.75)), 4)
            
            # String statistics (for non-numeric columns)
            else:
                col_data['top_value'] = str(df[col].mode()[0]) if len(df[col].mode()) > 0 else 'N/A'
                col_data['top_value_frequency'] = int(df[col].value_counts().iloc[0]) if len(df[col].value_counts()) > 0 else 0
            
            column_stats[col] = col_data
        
        stats['column_statistics'] = column_stats
        
        return jsonify({'success': True, 'stats': stats}), 200
    
    except pd.errors.ParserError as e:
        return jsonify({'success': False, 'error': f'CSV parsing error: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error processing file: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True)
