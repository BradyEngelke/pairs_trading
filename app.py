# command line statement to start local server
# python -m SimpleHTTPServer 8857

# import data
import pandas as pd
import simfin as sf

# set up api connection to simfin
sf.set_data_dir('~/simfin_data/')
sf.set_api_key(api_key='free')

# download share prices, cash flow statements, and company info. Select columns of interest
shares = sf.load(dataset='shareprices', variant='daily', market='us')
shares = shares.set_index(['Ticker', 'Date'])
shares = shares[['Close', 'Shares Outstanding', 'Volume', 'Dividend']]

cash = sf.load(dataset='cashflow', variant='annual', market='us')
cash = cash.set_index(['Ticker', 'Fiscal Year'])
cash = cash[['Shares (Basic)', 'Net Income/Starting Line', 'Net Cash from Operating Activities', 'Net Change in Cash']]

companies = sf.load(dataset='companies', market='us', index='Ticker')
industries = sf.load(dataset='industries')

# perform basic transformations
# 16 polarizing stock tickers selected for mock portfolio
bchips = ['GOOG', 'DIS', 'AAPL', 'BSX', 'CAT', 'CBS', 'FOX', 'LYFT', 'MDT',
          'MDB', 'MS', 'NEO', 'NVDA', 'PFG', 'STX', 'TDOC', 'TSLA', 'V']

# merge company info with shares dataset and cash flow dataset
blue_chips = pd.merge(companies.loc[bchips].reset_index(), industries, how='left', on='IndustryId')
bchip_shares = shares.loc[bchips] # daily time index
bchip_cash = cash.loc[bchips] # yearly time index

bchip_cash = bchip_cash.reset_index()
bchip_shares = bchip_shares.reset_index()

blue_chip_years = pd.merge(bchip_cash, blue_chips, how='left', on='Ticker')
blue_chip_days = pd.merge(bchip_shares, blue_chips, how='left', on='Ticker')

# perform pairs trading analysis
# create required master table for PE correlation analysis
shares = shares.loc[bchips]
shares = shares.reset_index()
del shares['Volume']
del shares['Dividend']
shares['year'] = shares['Date'].apply(lambda x: x[:4])

cash = cash.loc[bchips]
cash = cash.reset_index()
ni = cash[['Ticker', 'Fiscal Year', 'Net Income/Starting Line']]
ni = ni.rename(columns={'Fiscal Year': 'year', 'Net Income/Starting Line': 'net_income'})

shares['year'] = shares['year'].astype(int)
master = pd.merge(shares, ni, on=['Ticker', 'year'], how='left')
master = master.dropna()
del master['year']

# compute PE ratio
master['eps'] = master['net_income'] / master['Shares Outstanding']
master['pe'] = master['Close'] / master['eps']

# test for correlated pairs of stocks in regard to pe ratio
pe_ratios = master[['Ticker', 'Date', 'pe']]
# hypothesized pairs:
# GOOG <-> AAPL ; BSX <-> MDT ; NVDA <-> STX

# test pair by pair
# GOOG <-> AAPL
google = pe_ratios[pe_ratios['Ticker'] == 'GOOG']
apple =  pe_ratios[pe_ratios['Ticker'] == 'AAPL']
apple['Date'] = pd.to_datetime(apple['Date'])
google['Date'] = pd.to_datetime(google['Date'])
apple = apple[apple['Date'] >= '2014-03-27']
apple = apple.reset_index()
del apple['index']
google['pe'].corr(apple['pe']) # 0.515

# BSX <-> MDT
bs = pe_ratios[pe_ratios['Ticker'] == 'BSX']
bs['Date'] = pd.to_datetime(bs['Date'])
medt = pe_ratios[pe_ratios['Ticker'] == 'MDT']
medt['Date'] = pd.to_datetime(medt['Date'])
bs = bs[bs['Date'] >= '2014-01-02']
medt = medt[medt['Date'] <= '2018-12-31']
bs = bs.reset_index()
del bs['index']
medt = medt.reset_index()
del medt['index']
bs['pe'].corr(medt['pe']) # -0.036

# NVDA <-> STX
nvidia = pe_ratios[pe_ratios['Ticker'] == 'NVDA']
nvidia['Date'] = pd.to_datetime(nvidia['Date'])
seagate = pe_ratios[pe_ratios['Ticker'] == 'STX']
seagate['Date'] = pd.to_datetime(seagate['Date'])
nvidia = nvidia[nvidia['Date'] >= '2010-10-01']
seagate = seagate[seagate['Date'] <= '2018-12-31']
nvidia = nvidia.reset_index()
del nvidia['index']
seagate = seagate.reset_index()
del seagate['index']
nvidia['pe'].corr(seagate['pe']) # -0.016

# pair trade with ratio of Google pe ratio / Apple pe ratio
pair = google
pair = pair.merge(apple, how='inner', on=['Date'])
pair['pair_metric'] = pair['pe_x'] / pair['pe_y']
pair_past = pair[pair['Date'] < '2017-01-01'] # set start date of investment strategy to Jan 1st 2017
pair_past['pair_metric'].mean() # 1.895
pair_past['pair_metric'].std() # 0.417

# import dash & plotly modules
import dash
import dash_core_components as dcc
import dash_html_components as html
import plotly.express as px

# create figures
sector = blue_chip_years.groupby(by=['Sector', 'Fiscal Year']).median()
sector = sector.reset_index()
sector = sector.rename(columns={'Net Income/Starting Line': 'Median Net Income'})
fig1 = px.line(sector, x="Fiscal Year", y="Median Net Income", color='Sector')

blue_chip_recent_years = blue_chip_years[blue_chip_years['Fiscal Year'] > 2015]
company_recent_years = blue_chip_recent_years.groupby(by='Ticker').sum()
company_recent_years = company_recent_years[['Shares (Basic)', 'Net Income/Starting Line',
                            'Net Cash from Operating Activities', 'Net Change in Cash']]
company_recent_years = company_recent_years.rename(columns={'Net Income/Starting Line': '3-yr Total Net Income',
                                                    'Net Change in Cash': '3-yr Total Net Change in Cash'})
company_recent_years = company_recent_years.reset_index()
fig2 = px.scatter(company_recent_years, x='3-yr Total Net Change in Cash', y='3-yr Total Net Income', color='Ticker')

goog_apple_shares = shares[(shares['Ticker'] == 'GOOG')|(shares['Ticker'] == 'AAPL')]
goog_apple_shares = goog_apple_shares[goog_apple_shares['Date'] >= '2014-03-27']
goog_apple_shares = goog_apple_shares.rename(columns={'Close': 'Closing Price ($)'})
fig3 = px.line(goog_apple_shares, x="Date", y='Closing Price ($)', color='Ticker')

pair = pair.rename(columns={'pe_x': 'alphabet', 'pe_y': 'apple'})
pair2 = pd.melt(pair, id_vars=['Date'], value_vars=['alphabet', 'apple'])
pair2 = pair2.rename(columns={'variable': 'company', 'value': 'pe_ratio'})
fig4 = px.line(pair2, x="Date", y="pe_ratio", color='company')

pair['mean'] = 1.895 # pulling from avg ratio value prior to Jan 2017 from line 109
pair['upper_CI'] = 1.895 + 0.417 # pulling from standard dev value prior to Jan 2017 from line 110
pair['lower_CI'] = 1.895 - 0.417 # pulling from standard dev value prior to Jan 2017 from line 110
pair3 = pd.melt(pair, id_vars=['Date'], value_vars=['pair_metric', 'mean', 'upper_CI', 'lower_CI'])
pair4 = pair3[pair3['Date'] < '2017-01-01']
fig5 = px.line(pair4, x="Date", y='value', color='variable')
pair5 = pair3[pair3['Date'] >= '2017-01-01']
fig6 = px.line(pair5, x="Date", y='value', color='variable')


# create html dashboard

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

app.layout = html.Div(children=[

    html.H1(children='Investment Dashboard Focused on Pairs Trading', style={'color': 'green'}),

    html.Div(children='''
    Most individual investors stand little chance competing with top mutual funds and big banks on Wall Street. 
    Individual investors struggle sifting through quarterly balance sheets, Wall Street Journal articles, and 
    economic data to make informed investment decisions. Top mutual funds on the other hand have spent 
    the last 30 years hiring elite scientists to develop big data pipelines to ingest all of this information 
    which is then fed into advanced statistical models. These statistical models are components of a larger 
    autonomous system that makes hundreds of trading decisions a day with the objective of placing bets that win 
    slightly more than 50% of the time. This strategy may not seem glamorous, but most notably, it has 
    contributed to Renaissance Technologies posting industry leading returns for over 20 years. The dashboard 
    below attempts to bridge the sophistication gap between individual investors & top firms on Wall Street. 
    The underlying python script for this dashboard pulls financial data from SimFin’s API for the US market
    ranging back to January 2008, conducts data cleaning and transformations, and then generates two 
    visualizations that provide an overview of a mock portfolio’s performance. Below these plots, an 
    introduction to Pairs Trading is provided as a simple way for a novice investor to begin supplementing 
    their decision making with quantitative investment strategies.
    ''', style={'color': 'black', 'fontSize': 14}),

    html.H1(children='Portfolio Performance Overview', style={'color': 'green'}),

    html.Div(children='''
    Suppose a mock individual investor has selected 16 blue-chip stocks that she believes are going to perform 
    well over the long-term such as Apple, Disney, & Alphabet. Her first questions are likely to be, 
    which stocks and which sectors of stocks are performing well and which are not?
    ''', style={'color': 'black', 'fontSize': 14}),

    html.H2(children='Individual Stock Performance'),

    dcc.Graph(
        id='companies',
        figure=fig2
        ),

    html.Div(children='''
    The metrics chosen for the above illustration may not be optimal to base decisions off of but were chosen 
    as ideal given the data at hand. Assuming total net change in cash and total net income over the past 
    three years are useful metrics, the stocks closest to the top right corner are performing the best 
    relative to the other stocks.
    ''', style={'color': 'black', 'fontSize': 14}),

    html.H2(children='Sector Performance'),

    dcc.Graph(
            id='sectors',
            figure=fig1
                ),

    html.H1(children='Pairs Trading', style={'color': 'green'}),

    html.Div(children='''
    For Pairs Trading to be effective, you must identify two companies with stock prices, PE ratios, or any 
    other financial metric that are highly correlated with another. For this dashboard, the daily PE ratios 
    of Alphabet & Apple were used since the PE ratio is arguably a more accurate valuation of a stock’s worth 
    than its price. Furthermore, Alphabet & Apple had the highest correlation between their daily PE ratios 
    compared to other potential company pairs within the mock portfolio. Lets first visualize the stock prices 
    and PE ratios of Apple & Alphabet to distinguish how correlated their performance is. 
    For details on PE ratio calculations, please refer to the python script.
    ''', style={'color': 'black', 'fontSize': 14}),

    html.H2(children='Daily Closing Price of Alphabet & Apple'),
    dcc.Graph(
        id='shares',
        figure=fig3
    ),

    html.H2(children='Daily PE Ratio of Alphabet & Apple'),
    dcc.Graph(
            id='pairs',
            figure=fig4
                ),

    html.Div(children='''
    Alphabet’s PE ratio is clearly much more volatile than Apple’s. However, Alphabet's PE ratio consistently 
    reverts back to roughly twice the value of Apple’s PE ratio whenever it has varied substantially. This is 
    a good sign that the ratio of Alphabet's PE ratio divided by Apple’s PE ratio follows a 
    statistical phenomenon that can be exploited by Pairs Trading.
    ''', style={'color': 'black', 'fontSize': 14}),

    html.H2(children='Establishing Pair Metric Mean & Confidence Interval'),

    html.Div(children='''
    For this example, let’s say the investor wants to begin implementing Pairs Trading on January 1st, 2017. 
    To set up the strategy, the investor needs to compute the daily ratio of Alphabet’s PE ratio divided 
    by Apple’s PE ratio for all days historical data was collected, which will be termed the “pair metric”. 
    The mean and standard deviation of the pair metric can then be computed and used as process control 
    parameters to base investment decisions off of.
   ''', style={'color': 'black', 'fontSize': 14}),
    dcc.Graph(
            id='pairs_ratio',
            figure=fig5
                ),
    html.Div(children='''
    Note, the upper & lower confidence intervals were computed as one standard deviation away from the mean.
    ''', style={'color': 'black', 'fontSize': 14}),

    html.H2(children='Future Investment Strategy'),

    html.Div(children='''
    The investor can now compare the new daily pair metric against the historical mean and confidence interval 
    to determine whether an investment should be made. If the new daily pair metric is within the confidence 
    interval, then no trades should be made. If a new daily pair metric falls outside of the confidence 
    interval, then our investor can be confident that the pair metric has deviated a substantial distance 
    away from its usual state and will revert back to the mean eventually. When this deviation is detected, 
    the investor should identify whether Alphabet’s PE ratio or Apple’s PE ratio is causing the pair metric 
    to deviate and short the identified stock if it is overvalued and long that stock if it is undervalued. 
    Seeing that Alphabet’s PE ratio is more volatile than Apple’s PE ratio, Alphabet stock is likely the 
    security that our investor should be trading to leverage this mean-reversion process. For example, 
    all of 2017 our investor would have observed a pair metric above the upper confidence limit. After 
    referring to the Daily PE Ratio of Alphabet & Apple plot above, a huge jump in Alphabet’s PE ratio is 
    seen while Apple’s PE ratio stayed relatively stable during 2017. This indicates that Alphabet’s PE ratio 
    inflated the pair metric. In this case, our investor would short Alphabet stock until the pair metric 
    reverted back near the mean which happened in January 2018.
    ''', style={'color': 'black', 'fontSize': 14}),

    dcc.Graph(
            id='pairs_trading',
            figure=fig6
            ),

    html.Div(children='''
    This dashboard is a prototype of what it would look like for an individual investor to incorporate 
    quantitative investment strategies into their decision-making process. To enhance the Pairs Trading 
    technique shown above the investor would want to find two stocks that have a correlation between their
    PE ratio’s that is as close to 1 as possible (correlation between Alphabet & Apple’s PE ratios was only 0.515).
    The confidence interval should also be tuned to determine how many standard deviations away from the mean
    is optimal for making investment decisions (1 standard deviation was used). The historical time duration 
    used for computing the pair metric mean/standard deviation, and for how long into the future these statistics 
    would be useful, are also important considerations (January 1st, 2017 was chosen as a simple cutoff). 
    An algorithm that captures the rules-based trading logic in the above paragraph could be implemented to 
    evolve this dashboard into a more complete solution as well.
    ''', style={'color': 'black', 'fontSize': 14})
    ])

# run app
if __name__ == '__main__':
    app.run_server(port=8857)



