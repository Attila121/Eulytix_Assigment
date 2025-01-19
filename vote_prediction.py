import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
import seaborn as sns
import matplotlib.pyplot as plt
from datetime import datetime
import re
import glob

def calculate_senator_history(df, current_measure):
    """Calculate historical voting patterns for senators before the current measure"""
    current_date = pd.to_datetime(df[df['Measure_Number'] == current_measure]['Date'].iloc[0])
    previous_votes = df[pd.to_datetime(df['Date']) < current_date]
    
    if len(previous_votes) == 0:
        return {}, 0
    
    # Calculate senator voting patterns
    senator_patterns = {}
    for senator in df['Senator'].unique():
        if pd.isna(senator):
            continue
            
        senator_votes = previous_votes[previous_votes['Senator'] == senator]
        if len(senator_votes) > 0:
            yea_rate = (senator_votes['Vote'] == 'Yea').mean()
            participation_rate = (senator_votes['Vote'] != 'Not Voting').mean()
            senator_patterns[senator] = {
                'historical_yea_rate': yea_rate,
                'historical_participation': participation_rate,
                'vote_count': len(senator_votes)
            }
    
    # Calculate agreement scores between senators
    if len(senator_patterns) > 0:
        avg_agreement = calculate_senator_agreement(previous_votes)
    else:
        avg_agreement = 0
        
    return senator_patterns, avg_agreement

def calculate_senator_agreement(votes_df):
    """Calculate average agreement between senators"""
    agreement_scores = []
    senators = votes_df['Senator'].unique()
    
    for i, sen1 in enumerate(senators[:-1]):
        for sen2 in senators[i+1:]:
            # Get common votes
            votes1 = votes_df[votes_df['Senator'] == sen1].set_index('Measure_Number')['Vote']
            votes2 = votes_df[votes_df['Senator'] == sen2].set_index('Measure_Number')['Vote']
            
            # Calculate agreement on common measures
            common_measures = set(votes1.index) & set(votes2.index)
            if common_measures:
                agreement = sum((votes1[m] == votes2[m]) for m in common_measures) / len(common_measures)
                agreement_scores.append(agreement)
    
    return np.mean(agreement_scores) if agreement_scores else 0

def extract_quarter(month):
    """Convert month to fiscal quarter"""
    return (month - 1) // 3 + 1

def validate_data(df):
    """Validate input data"""
    if df.empty:
        raise ValueError("Empty dataframe")
    required_cols = ['Date', 'Result', 'Measure_Number', 'Measure_Title', 'Senator', 'Vote']
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    return True

def prepare_enhanced_features(df):
    """Create enhanced feature set including senator history"""
    if not validate_data(df):
        return pd.DataFrame()
    
    measures = []
    for measure_num in df['Measure_Number'].unique():
        if pd.isna(measure_num):
            continue
            
        measure_data = df[df['Measure_Number'] == measure_num]
        if len(measure_data) == 0:
            continue
            
        # Get base features
        feature_dict = {
            'Measure_Number': measure_num
        }
        
        # Time features
        date_str = measure_data['Date'].iloc[0]
        if pd.notna(date_str):
            date_obj = datetime.strptime(date_str, "%B %d, %Y, %I:%M %p")
            feature_dict.update({
                'fiscal_quarter': extract_quarter(date_obj.month),
                'hour': date_obj.hour,
                'is_late_night': 1 if (date_obj.hour >= 22 or date_obj.hour <= 4) else 0,
                'is_weekend': 1 if date_obj.weekday() >= 5 else 0,
                'days_to_fiscal_end': (date_obj.replace(month=9, day=30) - date_obj).days % 365
            })
        
        # Measure type features
        measure_title = measure_data['Measure_Title'].iloc[0]
        if pd.notna(measure_title):
            title = str(measure_title).lower()
            feature_dict.update({
                'is_appropriation': 1 if 'appropriation' in title else 0,
                'is_amendment': 1 if 'amendment' in title else 0,
                'is_authorization': 1 if 'authorization' in title else 0,
                'title_length': len(title),
                'is_emergency': 1 if 'emergency' in title else 0
            })
        
        # Historical senator patterns
        senator_history, avg_agreement = calculate_senator_history(df, measure_num)
        if senator_history:
            # Aggregate senator history
            feature_dict.update({
                'avg_historical_yea_rate': np.mean([s['historical_yea_rate'] 
                                                  for s in senator_history.values()]),
                'avg_historical_participation': np.mean([s['historical_participation'] 
                                                       for s in senator_history.values()]),
                'senator_agreement_score': avg_agreement,
                'active_senators': len(senator_history)
            })
        
        # Historical patterns
        previous_votes = df[pd.to_datetime(df['Date']) < pd.to_datetime(date_str)]
        if len(previous_votes) > 0:
            similar_type_votes = previous_votes[
                previous_votes['Measure_Number'].str.startswith(
                    str(measure_num).split('.')[0], na=False
                )
            ]
            feature_dict.update({
                'prev_measures_count': len(previous_votes),
                'prev_pass_rate': (previous_votes['Result'].str.contains(
                    'Agreed|Passed|Confirmed', na=False
                )).mean(),
                'similar_type_pass_rate': (similar_type_votes['Result'].str.contains(
                    'Agreed|Passed|Confirmed', na=False
                )).mean() if len(similar_type_votes) > 0 else 0
            })
        
        # Target variable
        feature_dict['Passed'] = 1 if measure_data['Result'].iloc[0] in df['Result'][
            df['Result'].str.contains('Agreed|Passed|Confirmed', na=False)
        ].unique() else 0
        
        measures.append(feature_dict)
    
    return pd.DataFrame(measures)

def train_model(X, y):
    """Train and evaluate the model"""
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    rf = RandomForestClassifier(
        n_estimators=200, 
        max_depth=10,
        random_state=42,
        class_weight='balanced'
    )
    rf.fit(X_train, y_train)
    
    return {
        'model': rf,
        'train_score': rf.score(X_train, y_train),
        'test_score': rf.score(X_test, y_test),
        'feature_importance': pd.DataFrame({
            'feature': X.columns,
            'importance': rf.feature_importances_
        }).sort_values('importance', ascending=False),
        'X_test': X_test,
        'y_test': y_test
    }

def main():
    try:
        print("Loading and processing data...")
        senate_votes_files = glob.glob('./senate_votes/*/*.csv')
        if not senate_votes_files:
            raise FileNotFoundError("No vote data files found")
            
        df = pd.concat([pd.read_csv(f) for f in senate_votes_files], ignore_index=True)
        
        print("\n=== Creating Enhanced Features ===")
        features_df = prepare_enhanced_features(df)
        
        if len(features_df) < 2:
            raise ValueError("Not enough valid measures for analysis")
            
        # Drop any columns that are all NA
        features_df = features_df.dropna(axis=1, how='all')
        
        # Prepare for modeling
        feature_cols = [col for col in features_df.columns 
                       if col not in ['Measure_Number', 'Passed']]
        
        X = features_df[feature_cols]
        y = features_df['Passed']
        
        print("\nFeatures being used:")
        for col in X.columns:
            print(f"- {col}")
        
        print("\n=== Training Model ===")
        results = train_model(X, y)
        
        print("\nModel Performance:")
        print(f"Training Score: {results['train_score']:.3f}")
        print(f"Test Score: {results['test_score']:.3f}")
        
        print("\nTop 10 Most Important Features:")
        print(results['feature_importance'].head(10))
        
        print("\nClassification Report:")
        y_pred = results['model'].predict(results['X_test'])
        print(classification_report(results['y_test'], y_pred))
        
        plt.figure(figsize=(12, 8))
        top_10_features = results['feature_importance'].nlargest(10, 'importance')
        sns.barplot(
            x='importance',
            y='feature',
            data=top_10_features
        )
        plt.title('Top 10 Most Important Features in Vote Prediction')
        plt.tight_layout()
        plt.savefig('feature_importance.png')
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return

if __name__ == "__main__":
    main()