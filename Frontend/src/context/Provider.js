import React, { createContext, useReducer, useState } from 'react';
import favInitialState from './initialState/favInitialState';
import favs from './reducers/favs';

export const GlobalContext = createContext({});

export const GlobalProvider = ({children}) => {
    const [favState, favDispatch] = useReducer(favs, favInitialState);

    return (
        <GlobalContext.Provider value = {{favState, favDispatch}}>
            {children}
        </GlobalContext.Provider>
    )
}
