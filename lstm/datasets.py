from torch.utils.data import Dataset, DataLoader
import torch
import numpy as np
import pandas as pd
import pytorch_lightning as pl
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split


class TimeseriesDataset(Dataset):
    '''
    Custom Dataset subclass. 
    Serves as input to DataLoader to transform X 
      into sequence data using rolling window. 
    DataLoader using this dataset will output batches 
      of `(batch_size, seq_len, n_features)` shape.
    Suitable as an input to RNNs. 
    '''
    def __init__(self, X: np.ndarray, y: np.ndarray, seq_len: int = 1):
        self.X = torch.tensor(X).float()
        self.y = torch.tensor(y).float()
        self.seq_len = seq_len

    def __len__(self):
        return self.X.__len__() - (self.seq_len-1)

    def __getitem__(self, index):
        x = self.X[index:index+self.seq_len]
        y = self.y[index+self.seq_len-1]
        return x, y


class PowerConsumptionDataModule(pl.LightningDataModule):
    '''
    PyTorch Lighting DataModule subclass:
    https://pytorch-lightning.readthedocs.io/en/latest/datamodules.html

    Serves the purpose of aggregating all data loading 
      and processing work in one place.
    '''
    
    def __init__(self, seq_len = 1, batch_size = 128, num_workers=0):
        super().__init__()
        self.seq_len = seq_len
        self.batch_size = batch_size
        self.num_workers = num_workers
        self.X_train = None
        self.y_train = None
        self.X_val = None
        self.y_val = None
        self.X_test = None
        self.X_test = None
        self.columns = None
        self.preprocessing = None

    def prepare_data(self):
        pass

    def setup(self, stage=None):
        '''
        Data is resampled to hourly intervals.
        Both 'np.nan' and '?' are converted to 'np.nan'
        'Date' and 'Time' columns are merged into 'dt' index
        '''

        if stage == 'fit' and self.X_train is not None:
            return
        if stage == 'test' and self.X_test is not None:
            return
        if stage is None and self.X_train is not None and self.X_test is not None:  
            return
        
        path = '/Users/francescocolonnese/cs145proj/data/train_trendency.csv'
        
        df = pd.read_csv(
            path, 
            sep=',', 
            parse_dates={'dt' : ['Date']}, 
            infer_datetime_format=True, 
            low_memory=False, 
            na_values=['nan','?'], 
            index_col='dt'
        )
        # df.Province_State = df.Province_State.map( 
        #     {
        #         'Arizona':0 , 
        #         'California':1, 
        #         'Texas':2, 
        #         'Alaska':3,
        #         'Arizona':4,
        #         'Arkansas':5,
        #         'California':6,
        #         'Colorado':7,
        #         'Connecticut': 8,
        #         'Delaware': 9,
        #         'District Of Columbia': 9,
        #         'Florida': 10,
        #         'Georgia': 11,
        #         'Guam': 12,
        #         'Hawaii': 13,
        #         'Idaho': 14,
        #         'Illinois': 15,
        #         'Indiana': 16,
        #         'Iowa': 17,
        #         'Kansas': 18, 
        #         'Kentucky': 19, 
        #         'Louisiana': 20, 
        #         'Maine': 21, 
        #         'Maryland': 22, 
        #         'Massachusetts': 23,
        #         'Michigan': 24, 
        #         'Minnesota': 25, 
        #         'Mississippi': 26, 
        #         'Missouri': 27, 
        #         'Montana': 28, 
        #         'Nebraska': 29, 
        #         'Nevada': 30, 
        #         'New Hampshire': 31, 
        #         'New Jersey': 32, 
        #         'New Mexico': 33, 
        #         'New York': 34,
        #         'North Carolina': 35, 
        #         'North Dakota': 36, 
        #         'Ohio': 37, 
        #         'Oklahoma': 38, 
        #         'Oregon': 39, 
        #         'Palau': 40, 
        #         'Pennsylvania': 41, 
        #         'Rhode Island': 42,
        #         'South Carolina': 43, 
        #         'South Dakota': 44, 
        #         'Tennessee': 45, 
        #         'Texas': 46, 
        #         'Utah': 47, 
        #         'Vermont': 48,
        #         'Virginia': 49, 
        #         'Washington': 50, 
        #         'West Virginia': 51, 
        #         'Wisconsin': 52, 
        #         'Wyoming': 53
        #     } )
        df = df.sort_values(by=['Province_State', 'dt'])

        df = df.drop(['Unnamed: 0', 'Recovered', 'Active', 'Incident_Rate',
                      'Total_Test_Results', 'Case_Fatality_Ratio', 'Testing_Rate', 'Province_State'], axis=1)
        X = df.dropna().copy()
        print(X)
        y = X['Deaths'].shift(-1).ffill()
        self.columns = X.columns

        X_cv, X_test, y_cv, y_test = train_test_split(
            X, y, test_size=0.10, shuffle=False
        )

        X_train, X_val, y_train, y_val = train_test_split(
            X_cv, y_cv, test_size=0.05, shuffle=False
        )

        preprocessing = StandardScaler()
        preprocessing.fit(X_train)

        if stage == 'fit' or stage is None:
            self.X_train = preprocessing.transform(X_train)
            self.y_train = y_train.values.reshape((-1, 1))
            self.X_val = preprocessing.transform(X_val)
            self.y_val = y_val.values.reshape((-1, 1))

        if stage == 'test' or stage is None:
            self.X_test = preprocessing.transform(X_test)
            self.y_test = y_test.values.reshape((-1, 1))

    def train_dataloader(self):
        train_dataset = TimeseriesDataset(self.X_train, 
                                          self.y_train, 
                                          seq_len=self.seq_len)
        train_loader = DataLoader(train_dataset,
                                  batch_size = self.batch_size,
                                  shuffle = False,
                                  num_workers = self.num_workers)
        
        return train_loader

    def val_dataloader(self):
        val_dataset = TimeseriesDataset(self.X_val,
                                        self.y_val,
                                        seq_len=self.seq_len)
        val_loader = DataLoader(val_dataset,
                                batch_size=self.batch_size,
                                shuffle=False,
                                num_workers=self.num_workers)

        return val_loader

    def test_dataloader(self):
        test_dataset = TimeseriesDataset(self.X_test,
                                         self.y_test,
                                         seq_len=self.seq_len)
        test_loader = DataLoader(test_dataset,
                                 batch_size=self.batch_size,
                                 shuffle=False,
                                 num_workers=self.num_workers)

        return test_loader
