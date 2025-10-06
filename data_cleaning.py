#%%
import pandas as pd
import numpy as np

#%%
sheet_name = ['Steel','Giaheo','Catra','Commodities', 'Textile','Container']
# Skip textile and container for now

#%% Preparing non-Bloomberg data
# Sheet
sheet_1 = 'Steel'
steel_df = pd.read_excel('data/NonBBG_data.xlsx', sheet_name=sheet_1)
steel_df = steel_df.melt(id_vars=['Dates'],value_vars = steel_df.columns[1:],var_name='Ticker', value_name='Price')
steel_df.rename(columns={'Dates':'Date'}, inplace=True)
steel_df = steel_df.sort_values('Date', ascending = True)

# Gia heo
sheet_2 = 'Giaheo'
heo_df = pd.read_excel('data/NonBBG_data.xlsx', sheet_name=sheet_2)
heo_df.drop(columns=['Region','Low','High'], inplace=True)
heo_df.rename(columns={'Average':'Price','Name':'Ticker'}, inplace=True)
heo_df = heo_df.sort_values('Date', ascending = True)

# Ca tra
sheet_3 = 'Catra'
fish_df = pd.read_excel('data/NonBBG_data.xlsx', sheet_name=sheet_3)
fish_df.drop(columns=['Market','Ticker'], inplace=True)
fish_value_df = fish_df[['Date','Code','Value']].copy()
fish_value_df['Code'] = fish_value_df['Code'] + '_Value'
fish_value_df.rename(columns={'Value':'Price'}, inplace=True)
fish_asp_df = fish_df[['Date','Code','Selling price']].copy()
fish_asp_df['Code'] = fish_asp_df['Code'] + '_ASP'
fish_asp_df.rename(columns={'Selling price':'Price'}, inplace=True)
fish_df = pd.concat([fish_value_df, fish_asp_df])
fish_df.rename(columns={'Code':'Ticker'}, inplace=True)
fish_df = fish_df.sort_values('Date', ascending = True)

# Commodities
sheet_4 = 'Commodities'
commo_df = pd.read_excel('data/NonBBG_data.xlsx', sheet_name=sheet_4)
commo_df = commo_df.melt(id_vars=['Date'],value_vars = commo_df.columns[1:],var_name='Ticker', value_name='Price')
commo_df = commo_df.sort_values('Date', ascending = True)

# Container
sheet_5 = 'Container'
container_df = pd.read_excel('data/NonBBG_data.xlsx', sheet_name=sheet_5)
container_df.rename(columns={'Row Labels':'Date'}, inplace=True)
container_df = container_df.melt(id_vars=['Date'],value_vars = container_df.columns[1:],var_name='Ticker', value_name='Price')
container_df = container_df.sort_values('Date', ascending = True)

# Merge
merged_df = pd.concat([steel_df, heo_df, fish_df, commo_df, container_df])
merged_df['Ticker'] = merged_df['Ticker'].str.strip()

#%% Bloomberg Data
df = pd.read_csv('data/BBG_data.csv')
df.columns = df.columns.str.strip()
df.rename(columns={'Commodities':'Ticker'}, inplace=True)
df['Ticker'] = df['Ticker'].str.strip()
df['Date'] = pd.to_datetime(df['Date'])

final_df = pd.concat([merged_df, df])

# Classification
classification = pd.read_excel('commo_list.xlsx')
classification['Item'] = classification['Item'].str.strip()

class_list = classification.set_index('Item')['Group'].to_dict()
final_df['Group'] = final_df['Ticker'].map(class_list)

# Add Region mapping
region_list = classification.set_index('Item')['Region'].to_dict()
final_df['Region'] = final_df['Ticker'].map(region_list)

# Add Sector mapping
sector_list = classification.set_index('Item')['Sector'].to_dict()
final_df['Sector'] = final_df['Ticker'].map(sector_list)

# # Remove ungrouped tickers
# final_df = final_df[~final_df['Group'].isna()]

#%% Detect duplicates
duplicates = final_df[final_df.duplicated(subset=['Date', 'Ticker'], keep=False)]
duplicates = duplicates.sort_values(['Date', 'Ticker'])
final_df = final_df.drop_duplicates(subset=['Date', 'Ticker'], keep='last')


# final_df.to_csv('data/cleaned_data.csv', index=False)

#%% Ticker list analysis
all_ticker_list = final_df.Ticker.unique().tolist()
classified_ticker_list = classification.Item.unique().tolist()
missing_in_data_ticker = [ticker for ticker in classified_ticker_list if ticker not in all_ticker_list]
unclassified_ticker = [ticker for ticker in all_ticker_list if ticker not in classified_ticker_list]

# Create ticker status dataframe
bbg_ticker_list = df.Ticker.unique().tolist()

ticker_status_df = pd.DataFrame({
    'Ticker': sorted(all_ticker_list),
    'Source': ['BBG' if ticker in bbg_ticker_list else 'Non_BBG' for ticker in sorted(all_ticker_list)],
    'Is_Classified': [ticker in classified_ticker_list for ticker in sorted(all_ticker_list)]
})

ticker_status_df['Is_Classified'] = ticker_status_df['Is_Classified'].astype(int)  # Convert boolean to string for better readability

# ticker_status_df.to_csv('ticker_status.csv', index=False)