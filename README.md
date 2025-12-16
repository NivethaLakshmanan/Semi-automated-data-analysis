# Semi-Automated Data Analysis System

## Overview
This project is a semi-automated data analysis system built using Flask, MySQL, and Power BI.

Users manually upload Excel or CSV files through a web interface.  
The backend cleans the data and stores it into a MySQL database.  
Power BI is then used to create dashboards from the database.

## Project Structure
ANALYSIS/
├── back.py
├── templates/
│   └── analy.html
├── uploads/
│   ├── Raw/
│   └── Cleaned/

## What This Project Does
- Manual upload of Excel / CSV files
- Data cleaning using Pandas
- Stores cleaned data in MySQL
- Replaces old data when updated files are uploaded
- Data can be visualized using Power BI

## Technologies Used
- Python (Flask)
- Pandas
- MySQL
- HTML & CSS
- Power BI

## How to Run
1. Start MySQL server
2. Run:
   python back.py
3. Open browser:
   http://127.0.0.1:5000
4. Upload the files
5. Refresh the Power BI

## Current Limitations
- File upload is manual
- No automatic scheduling
- Dashboards refresh only after new upload

## Future Improvements
- Automated data ingestion
- Scheduled uploads
- Better error handling
