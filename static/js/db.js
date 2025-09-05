// IndexedDB Operations
const DB_NAME = "JiraTimesheetDB";
const DB_VERSION = 1;
const STORE_NAME = "appData";

class IndexedDBManager {
  constructor() {
    this.db = null;
  }

  async initDB() {
    try {
      // Check if IndexedDB is available
      if (!window.indexedDB) {
        throw new Error("Your browser doesn't support IndexedDB");
      }

      return new Promise((resolve, reject) => {
        const request = indexedDB.open(DB_NAME, DB_VERSION);

        request.onerror = (event) => {
          console.error("Error opening DB:", event.target.error);
          reject(event.target.error);
        };

        request.onsuccess = (event) => {
          this.db = event.target.result;

          // Handle connection loss
          this.db.onclose = () => {
            console.log("DB connection lost. Attempting to reconnect...");
            this.db = null;
            this.initDB().catch(console.error);
          };

          // Handle version change
          this.db.onversionchange = (event) => {
            this.db.close();
            console.log("DB version changed. Please reload the page.");
            alert(
              "Database version changed. Please reload the page for updates."
            );
          };

          resolve(this.db);
        };

        request.onupgradeneeded = (event) => {
          const db = event.target.result;
          if (!db.objectStoreNames.contains(STORE_NAME)) {
            const store = db.createObjectStore(STORE_NAME);
            store.createIndex("timestamp", "timestamp", { unique: false });
          }
        };

        request.onblocked = (event) => {
          console.warn(
            "DB upgrade blocked. Please close other tabs with this site open."
          );
          alert(
            "Database upgrade blocked. Please close other tabs with this site open."
          );
        };
      });
    } catch (error) {
      console.error("Failed to initialize database:", error);
      throw error;
    }
  }

  async getData(key) {
    try {
      if (!this.db) await this.initDB();

      return new Promise((resolve, reject) => {
        const transaction = this.db.transaction([STORE_NAME], "readonly");
        const store = transaction.objectStore(STORE_NAME);
        const request = store.get(key);

        transaction.oncomplete = () => {
          resolve(request.result);
        };

        transaction.onerror = () => {
          reject(transaction.error);
        };

        request.onerror = () => {
          reject(request.error);
        };
      });
    } catch (error) {
      console.error(`Error getting data for key ${key}:`, error);
      throw error;
    }
  }

  async setData(key, value) {
    try {
      if (!this.db) await this.initDB();

      // Add timestamp to the stored data
      const dataToStore = {
        ...value,
        timestamp: new Date().getTime(),
      };

      return new Promise((resolve, reject) => {
        const transaction = this.db.transaction([STORE_NAME], "readwrite");
        const store = transaction.objectStore(STORE_NAME);
        const request = store.put(dataToStore, key);

        transaction.oncomplete = () => {
          resolve();
        };

        transaction.onerror = () => {
          reject(transaction.error);
        };

        request.onerror = () => {
          reject(request.error);
        };
      });
    } catch (error) {
      console.error(`Error setting data for key ${key}:`, error);
      throw error;
    }
  }

  async deleteData(key) {
    if (!this.db) await this.initDB();
    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction([STORE_NAME], "readwrite");
      const store = transaction.objectStore(STORE_NAME);
      const request = store.delete(key);

      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });
  }
}

// Create singleton instance
export const dbManager = new IndexedDBManager();
