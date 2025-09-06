import React from 'react';
import Header from './components/Header';
import FileUpload from './components/FileUpload';
import ProcessingStatus from './components/ProcessingStatus';
import ResultsDisplay from './components/ResultsDisplay';
import useImageProcessing from './hooks/useImageProcessing';

function App() {
  const { processImage, result, error, isProcessing } = useImageProcessing();

  const handleFileSelect = async (file: File) => {
    await processImage(file);
  };

  return (
    <div className="bg-[#1a102b] min-h-screen">
      <div className="layout-container flex h-full grow flex-col">
        <Header />
        <main className="flex flex-1 justify-center py-12 px-4 sm:px-6 lg:px-8">
          <div className="w-full max-w-4xl space-y-10">
            <div className="text-center">
              <h2 className="text-4xl font-bold text-white tracking-tight sm:text-5xl">Analyze Your Swedish Textbook Page</h2>
              <p className="mt-4 text-lg leading-8 text-gray-300">Upload an image to get an instant analysis of the text, grammar, and vocabulary.</p>
            </div>

            <FileUpload onFileSelect={handleFileSelect} isProcessing={isProcessing} />

            {isProcessing && <ProcessingStatus isProcessing={isProcessing} />}

            {(result || error) && <ResultsDisplay result={result} error={error} />}
          </div>
        </main>
      </div>
    </div>
  );
}

export default App;
