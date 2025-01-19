# Eulytix Assignment

## Task 1: U.S. Senate Roll Call Vote Data Collection

### Overview
This project automates the collection of U.S. Senate roll call votes, focusing on creating a comprehensive dataset that includes individual senator votes, party affiliations, voting outcomes, and metadata such as vote results and measure details.

---

### Approach

#### Data Source Selection
After evaluating available options for collecting U.S. Senate roll call vote data, I identified two potential approaches:
1. **Web Scraping** - Direct collection from senate.gov
2. **API Integration** - Using third-party APIs

I chose web scraping from senate.gov because:
- It provides direct access to authoritative source data
- The website structure is consistent and well-organized
- No API key or authentication required
- Complete control over data collection process

---

### Implementation Strategy

#### 1. Website Analysis
First examined the senate.gov website structure:
- Main vote list page for the year 2024: `/legislative/LIS/roll_call_lists/vote_menu_118_2.htm`
- Individual vote pages contain detailed senator-level data
- Identified key HTML elements and data structures

#### 2. Technical Architecture
Developed a modular scraping solution using:
- **Selenium** for dynamic page interaction (handling dropdown selection)
- **BeautifulSoup** for HTML parsing
- **Pandas** for data structuring and export
- **Logging** for operation monitoring and debugging

#### 3. Data Collection Process
Implemented a multi-stage collection pipeline:
1. Navigate to main vote list page
2. Select "All" votes from dropdown menu
3. Extract vote links from main table
4. Visit each vote's detail page
5. Parse and store voting records
6. Save structured data in CSV format.

#### Technical Tools
- **Selenium**: Automates interaction with dropdown menus.
- **BeautifulSoup**: Extracts structured data.
- **Pandas**: Organizes and exports data.

#### Data Output
- Two row types: Metadata (e.g., vote date, measure title) and individual votes (e.g., senator, party, state, vote).
- Output format: CSV for compatibility and ease of use.

#### Scrape More Data
To gather additional data for Task 2, I created `scrape_multiple_years.py` to scrape data from multiple years concurrently using multiple threads.

---

## Assumptions Made

1. **Website Structure Stability**
   - Senate.gov maintains consistent HTML structure
   - Key element IDs and classes remain unchanged

2. **Data Consistency**
   - Vote results follow standard formats
   - Senator information (party, state) is consistently presented

3. **Access Requirements**
   - Public access to voting records remains available
   - No rate limiting affects data collection

## Implementation Details

### Data Format
Structured the output as CSV with two types of rows:
- **Metadata**: Vote date, result, measure details
- **Vote Records**: Individual senator votes with party and state

### Error Handling
- Implemented robust error handling for network issues
- Added logging for debugging and monitoring
- Included retry logic for failed requests

### Performance Considerations
- Added appropriate delays between requests
- Implemented parallel processing for efficiency
- Cached data to prevent data loss during collection

---

Given additional time and resources, I would implement:

1. **Enhanced Robustness**
   - Add automated tests for data validation
   - Implement failover mechanisms
   - Add data integrity checks

2. **Performance Optimization**
   - Optimize parallel processing
   - Implement smarter rate limiting
   - Add incremental update capabilities

3. **Data Enhancement**
   - Add historical vote pattern analysis
   - Include bill category classification
   - Link to external bill information

4. **Monitoring & Maintenance**
   - Add automated monitoring system
   - Implement change detection for website updates
   - Create data quality dashboards


---

## Task 2: Predicting U.S. Senate Roll Call Vote Outcomes

### Overview
This task focuses on developing a machine learning model to predict whether a U.S. Senate measure will pass or fail using the dataset collected in Task 1.

---

### Approach

#### Data Preparation
1. **Measure Characteristics**
   - Type classification (Bill, Amendment, Resolution)
   - Title analysis for key terms and topics
   - Title length as complexity indicator
   - Emergency/appropriation flags

2. **Temporal Features**
   - Fiscal quarters 
   - Time of day (captures urgency patterns in late-night votes)
   - Weekend vs. weekday votes
   - Days to fiscal year end

3. **Historical Patterns**
   - Previous measures count
   - Historical pass rates for similar measure types
   - Historical voting patterns by measure type

4. **Data Split**:
   - Training (80%) and testing (20%) subsets.

---

#### Model Selection
- Chose **Random Forest Classifier** for:
  - Ability to handle both numerical and categorical features
  - Feature importance insights
  - Resistance to overfitting
  - Good performance on moderate-sized datasets

---

### Results

#### Model Performance
- **Training Accuracy**: 96.4%
- **Testing Accuracy**: 59.0%
- The gap suggests overfitting, but this is expected given the complex political nature of voting and the lack of data

#### Feature Importance
Top features:
1. `similar_type_pass_rate` (21.3%)
2. `prev_measures_count` (17.2%)
3. `prev_pass_rate` (15.6%)

#### Classification Report
| Metric       | Passed (1) | Failed (0) | Overall |
|--------------|------------|------------|---------|
| Precision    | 65%        | 53%        | 59%     |
| Recall       | 56%        | 62%        | 59%     |
| F1-Score     | 60%        | 57%        | 59%     |

---

### Assumptions Made
1. **Historical Patterns**
   - Past voting behavior influences future votes
   - Similar types of measures tend to have similar outcomes

2. **Temporal Relevance**
   - Time-based features (e.g., fiscal quarters) affect voting patterns
   - Late-night or weekend votes may indicate different voting dynamics

3. **Measure Characteristics**
   - The type and complexity of measures influence outcomes
   - Emergency or appropriation measures may follow different patterns

---

### Discussion

#### Strengths
1. Effective feature engineering capturing historical and contextual data.
2. Transparent results with feature importance analysis.

#### Limitations
1. Small dataset limits generalization.
2. Moderate model performance (59% accuracy).

---

### Future Improvements
Given additional time and resources, I would:

1. **Feature Engineering**
   - Implement more sophisticated text analysis of measure titles
   - Add party dynamics and coalition analysis
   - Include senator relationship networks

2. **Model Enhancements**
   - Experiment with other algorithms (XGBoost, LightGBM)
   - Implement cross-validation
   - Add ensemble methods
   - Fine-tune hyperparameters

3. **Performance Optimization**
   - Address the training-test score gap
   - Implement better class balancing
   - Add confidence scores for predictions


---

### How to Run
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the scripts:

- Data Collection for 2024:
    ```bash
    python senate_vote_scrapper.py
    ```
- Prediction:
    ```bash
    python vote_prediction.py
    ```

- Additional data collection for more years:
   ```bash
    python scrape_multiple_years.py
    ```

## Technical Dependencies


- Python 3.8+
- Libraries:
    - Selenium
    - BeautifulSoup4
    - Pandas
    - Scikit-learn
    - Numpy
    - Matplotlib