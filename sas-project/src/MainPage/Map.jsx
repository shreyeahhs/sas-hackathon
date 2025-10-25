

function Map(){

    return (<>
    <div className="Map-container">
        <h1>Find your place</h1>
        <div className="map-wrap">
      <iframe
        title="Map"
        src="https://www.google.com/maps?q=51.5074,-0.1278&z=13&output=embed"
        loading="lazy"
        allowFullScreen
        referrerPolicy="no-referrer-when-downgrade"
      />
    </div>
        </div>
    </>)

}
export default Map;