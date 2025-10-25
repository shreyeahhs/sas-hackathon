import { useState } from 'react'
import {BrowserRouter, Route, Routes} from 'react-router-dom';
import Card from './MainPage/Cards';
import Footer from './MainPage/Footer';
import Introduction from './MainPage/Introduction';
import Map from './MainPage/Map';
import Vibe from './Plan/Vibe';



function App() {
  const [preferences, setPreferences] = useState({});

  return (
    <>

      
      <Routes>
           <Route path="/" element={<>
      <Introduction/>
      <Card/>
      <Map/>
      <Footer/>
      </>} />
        <Route path="/vibe" element={<Vibe />} />
        
      </Routes>
    
      


    </>
  )
}

export default App
