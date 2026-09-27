const DATABASE_NAME = "journi-local-documents";
const STORE_NAME = "journey-tickets";

type StoredTicket = {
  fileName: string;
  file: Blob;
};

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE_NAME, 1);
    request.onupgradeneeded = () => {
      request.result.createObjectStore(STORE_NAME);
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error("Local ticket storage could not be opened."));
  });
}

export async function saveJourneyTicket(file: File, journeyKey: string): Promise<void> {
  const database = await openDatabase();
  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = database.transaction(STORE_NAME, "readwrite");
      transaction.objectStore(STORE_NAME).put({ fileName: file.name, file }, journeyKey);
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error ?? new Error("The ticket could not be saved locally."));
      transaction.onabort = () => reject(transaction.error ?? new Error("The ticket could not be saved locally."));
    });
  } finally {
    database.close();
  }
}

export async function loadJourneyTicket(journeyKey: string): Promise<File | null> {
  const database = await openDatabase();
  try {
    const record = await new Promise<StoredTicket | undefined>((resolve, reject) => {
      const request = database.transaction(STORE_NAME, "readonly")
        .objectStore(STORE_NAME)
        .get(journeyKey);
      request.onsuccess = () => resolve(request.result as StoredTicket | undefined);
      request.onerror = () => reject(request.error ?? new Error("The saved ticket could not be read."));
    });
    return record ? new File([record.file], record.fileName, { type: record.file.type }) : null;
  } finally {
    database.close();
  }
}

export async function removeJourneyTicket(journeyKey: string): Promise<void> {
  const database = await openDatabase();
  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = database.transaction(STORE_NAME, "readwrite");
      transaction.objectStore(STORE_NAME).delete(journeyKey);
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error ?? new Error("The saved ticket could not be removed."));
      transaction.onabort = () => reject(transaction.error ?? new Error("The saved ticket could not be removed."));
    });
  } finally {
    database.close();
  }
}
