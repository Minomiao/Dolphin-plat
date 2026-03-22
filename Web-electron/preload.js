const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    getServerUrl: () => ipcRenderer.invoke('get-server-url'),
    selectDirectory: () => ipcRenderer.invoke('select-directory'),
    showSaveDialog: (options) => ipcRenderer.invoke('show-save-dialog', options),
    showOpenDialog: (options) => ipcRenderer.invoke('show-open-dialog', options),
    openExternal: (url) => ipcRenderer.invoke('open-external', url),
    
    onServerLog: (callback) => {
        ipcRenderer.on('server-log', (event, data) => callback(data));
    },
    
    onServerError: (callback) => {
        ipcRenderer.on('server-error', (event, data) => callback(data));
    },
    
    removeAllListeners: (channel) => {
        ipcRenderer.removeAllListeners(channel);
    }
});
