import { Monitor } from './components/Monitor'

// Global styles
const globalStyles = `
  * {
    box-sizing: border-box;
  }

  body {
    margin: 0;
    padding: 0;
    background-color: #1a1a2e;
  }

  ::-webkit-scrollbar {
    width: 8px;
    height: 8px;
  }

  ::-webkit-scrollbar-track {
    background: #0f3460;
  }

  ::-webkit-scrollbar-thumb {
    background: #1a4b8c;
    border-radius: 4px;
  }

  ::-webkit-scrollbar-thumb:hover {
    background: #2a5b9c;
  }
`

function App() {
  return (
    <>
      <style>{globalStyles}</style>
      <Monitor />
    </>
  )
}

export default App
