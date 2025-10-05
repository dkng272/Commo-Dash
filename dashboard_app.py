import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from commo_dashboard import create_equal_weight_index, create_weighted_index, create_regional_indexes

# Load data
@st.cache_data
def load_data():
    df = pd.read_csv('data/cleaned_data.csv')
    df['Date'] = pd.to_datetime(df['Date'])
    return df

@st.cache_data
def build_indexes(df):
    all_groups = df['Group'].unique()
    all_indexes = {}

    for group in all_groups:
        if group not in ['Pangaseus', 'Crack Spread']:
            all_indexes[group] = create_equal_weight_index(df, group)

    # Handle Crack Spread separately
    crack_spread_df = df[df['Group'] == 'Crack Spread'].copy()
    crack_spread_df = crack_spread_df.drop_duplicates(subset=['Date', 'Ticker'], keep='last')
    crack_pivot = crack_spread_df.pivot(index='Date', columns='Ticker', values='Price')
    crack_avg = crack_pivot.abs().mean(axis=1)
    all_indexes['Crack Spread'] = pd.DataFrame({
        'Date': crack_avg.index,
        'Index_Value': crack_avg.values
    })

    # Combine all indexes
    first_group = list(all_indexes.keys())[0]
    combined_df = all_indexes[first_group].copy()
    combined_df.rename(columns={'Index_Value': first_group}, inplace=True)

    for group in list(all_indexes.keys())[1:]:
        temp_df = all_indexes[group].copy()
        temp_df.rename(columns={'Index_Value': group}, inplace=True)
        combined_df = combined_df.merge(temp_df, on='Date', how='outer')

    combined_df = combined_df.sort_values('Date')
    combined_df = combined_df.ffill()

    # Regional indexes
    regional_indexes = create_regional_indexes(df)

    if len(regional_indexes) > 0:
        first_regional = list(regional_indexes.keys())[0]
        regional_combined_df = regional_indexes[first_regional].copy()
        regional_combined_df.rename(columns={'Index_Value': first_regional}, inplace=True)

        for key in list(regional_indexes.keys())[1:]:
            temp_df = regional_indexes[key].copy()
            temp_df.rename(columns={'Index_Value': key}, inplace=True)
            regional_combined_df = regional_combined_df.merge(temp_df, on='Date', how='outer')

        regional_combined_df = regional_combined_df.sort_values('Date')
        regional_combined_df = regional_combined_df.ffill()
    else:
        regional_combined_df = pd.DataFrame()

    return all_indexes, combined_df, regional_indexes, regional_combined_df

# Load data
df = load_data()
all_indexes, combined_df, regional_indexes, regional_combined_df = build_indexes(df)

# Streamlit Dashboard
st.title('Commodity Index Dashboard')

# Summary Table - Largest Swings
st.subheader('Largest Index Swings')

summary_data = []
for group in all_indexes.keys():
    index_data = combined_df[group].dropna()

    change_1d = ((index_data.iloc[-1] / index_data.iloc[-2]) - 1) * 100 if len(index_data) >= 2 else 0
    change_5d = ((index_data.iloc[-1] / index_data.iloc[-6]) - 1) * 100 if len(index_data) >= 6 else 0
    change_15d = ((index_data.iloc[-1] / index_data.iloc[-16]) - 1) * 100 if len(index_data) >= 16 else 0

    summary_data.append({
        'Group': group,
        '1D Change (%)': round(change_1d, 2),
        '5D Change (%)': round(change_5d, 2),
        '15D Change (%)': round(change_15d, 2),
        '1D Abs Swing': round(abs(change_1d), 2),
        '5D Abs Swing': round(abs(change_5d), 2),
        '15D Abs Swing': round(abs(change_15d), 2)
    })

summary_df = pd.DataFrame(summary_data)

col1, col2, col3 = st.columns(3)

with col1:
    st.write("**Top 10 - Largest 1D Swings**")
    top_1d = summary_df.sort_values('1D Abs Swing', ascending=False).head(10)
    st.dataframe(
        top_1d[['Group', '1D Change (%)']],
        hide_index=True
    )

with col2:
    st.write("**Top 10 - Largest 5D Swings**")
    top_5d = summary_df.sort_values('5D Abs Swing', ascending=False).head(10)
    st.dataframe(
        top_5d[['Group', '5D Change (%)']],
        hide_index=True
    )

with col3:
    st.write("**Top 10 - Largest 15D Swings**")
    top_15d = summary_df.sort_values('15D Abs Swing', ascending=False).head(10)
    st.dataframe(
        top_15d[['Group', '15D Change (%)']],
        hide_index=True
    )

st.divider()

# Sidebar for group selection
selected_group = st.sidebar.selectbox(
    'Select Commodity Group',
    options=sorted(list(all_indexes.keys()))
)

# Display ticker components
st.subheader(f'{selected_group} - Component Tickers')
tickers = df[df['Group'] == selected_group]['Ticker'].unique()
st.write(', '.join(sorted(tickers)))

# Plot the selected index
st.subheader(f'{selected_group} Index')

# Filter to only dates with valid data for this index
plot_df = combined_df[['Date', selected_group]].dropna()

fig = go.Figure()

fig.add_trace(go.Scatter(
    x=plot_df['Date'],
    y=plot_df[selected_group],
    mode='lines',
    name=selected_group,
    line=dict(width=2)
))

fig.update_layout(
    xaxis_title='Date',
    yaxis_title='Index Value' if selected_group != 'Crack Spread' else 'Average Absolute Value',
    hovermode='x unified',
    template='plotly_white',
    height=500
)

st.plotly_chart(fig, use_container_width=True)

# Show summary statistics
st.subheader('Performance Metrics')
index_data = combined_df[selected_group].dropna()
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric('Current Value', f'{index_data.iloc[-1]:.2f}')
with col2:
    change_1d = ((index_data.iloc[-1] / index_data.iloc[-2]) - 1) * 100 if len(index_data) >= 2 else 0
    st.metric('1D Change', f'{change_1d:.2f}%', delta=f'{change_1d:.2f}%')
with col3:
    change_5d = ((index_data.iloc[-1] / index_data.iloc[-6]) - 1) * 100 if len(index_data) >= 6 else 0
    st.metric('5D Change', f'{change_5d:.2f}%', delta=f'{change_5d:.2f}%')
with col4:
    change_15d = ((index_data.iloc[-1] / index_data.iloc[-16]) - 1) * 100 if len(index_data) >= 16 else 0
    st.metric('15D Change', f'{change_15d:.2f}%', delta=f'{change_15d:.2f}%')

# Regional Sub-Indexes
regional_keys = [key for key in regional_indexes.keys() if key.startswith(selected_group + ' - ')]

if len(regional_keys) > 0:
    st.subheader(f'{selected_group} - Regional Breakdown')

    # Create tabs for each region
    tabs = st.tabs([key.split(' - ')[1] for key in regional_keys])

    for i, (tab, regional_key) in enumerate(zip(tabs, regional_keys)):
        with tab:
            region_name = regional_key.split(' - ')[1]

            # Plot regional index
            plot_df_regional = regional_combined_df[['Date', regional_key]].dropna()

            fig_regional = go.Figure()
            fig_regional.add_trace(go.Scatter(
                x=plot_df_regional['Date'],
                y=plot_df_regional[regional_key],
                mode='lines',
                name=regional_key,
                line=dict(width=2)
            ))

            fig_regional.update_layout(
                xaxis_title='Date',
                yaxis_title='Index Value' if selected_group != 'Crack Spread' else 'Average Absolute Value',
                hovermode='x unified',
                template='plotly_white',
                height=400
            )

            st.plotly_chart(fig_regional, use_container_width=True)

            # Regional metrics
            regional_data = regional_combined_df[regional_key].dropna()
            col1r, col2r, col3r, col4r = st.columns(4)

            with col1r:
                st.metric('Current Value', f'{regional_data.iloc[-1]:.2f}')
            with col2r:
                change_1d_r = ((regional_data.iloc[-1] / regional_data.iloc[-2]) - 1) * 100 if len(regional_data) >= 2 else 0
                st.metric('1D Change', f'{change_1d_r:.2f}%', delta=f'{change_1d_r:.2f}%')
            with col3r:
                change_5d_r = ((regional_data.iloc[-1] / regional_data.iloc[-6]) - 1) * 100 if len(regional_data) >= 6 else 0
                st.metric('5D Change', f'{change_5d_r:.2f}%', delta=f'{change_5d_r:.2f}%')
            with col4r:
                change_15d_r = ((regional_data.iloc[-1] / regional_data.iloc[-16]) - 1) * 100 if len(regional_data) >= 16 else 0
                st.metric('15D Change', f'{change_15d_r:.2f}%', delta=f'{change_15d_r:.2f}%')

            # Show tickers in this region
            st.write(f"**Component Tickers ({region_name}):**")
            regional_tickers = df[(df['Group'] == selected_group) & (df['Region'] == region_name)]['Ticker'].unique()
            st.write(', '.join(sorted(regional_tickers)))
