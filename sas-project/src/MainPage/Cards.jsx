

function Cards(){

    return (<>
        <div className="cards-container">

        <span><h1> Recommended Activities</h1></span>
        <div className="Act-card">
            <img src="HorseshoeBar.jpg"/>
            <h4>Horseshoebar</h4>
            <div className="info">
            <i className="fa-solid fa-star"></i><p>: 4.3</p><br/>
            <i className="fa-solid fa-tag"></i><p>: £10 - 20</p><br/>
            <i className="fa-solid fa-location-dot"></i><p>: 0.6 miles</p><br/>
            <p>Adress: 17-19 Drury St, Glasgow G2 5AE</p>
            <button className="AddedPlan">Add to Plan <i class="fa-solid fa-plus"></i></button>
            </div>
        </div>
        
        <div className="Act-card">
            <img src="Popworld.jpg"/>
            <h4>Popworld</h4>
            <div className="info">
            <i className="fa-solid fa-star"></i><p>: 4.2</p><br/>
            <i className="fa-solid fa-tag"></i><p>: £20 - 30</p><br/>
            <i className="fa-solid fa-location-dot"></i><p>: 0.6 miles</p><br/>
            <p>Address: 114 W George St, Glasgow G2 1PS</p>
            <button className="AddedPlan">Add to Plan <i class="fa-solid fa-plus"></i></button>
            </div>
        </div>

        <div className="Act-card">
            <img src="Supercube.jpg"/>
            <h4>Supercube</h4>
            <div className="info">
            <i className="fa-solid fa-star"></i><p>: 4.4</p><br/>
            <i className="fa-solid fa-tag"></i><p>: £27.50 - 87.50 </p><br/>
            <i className="fa-solid fa-location-dot"></i><p>: 0.6 miles</p><br/>
            <p>Address: 104 Bath St, Glasgow G2 2EN</p>
            <button className="AddedPlan">Add to Plan <i class="fa-solid fa-plus"></i></button>
            </div>
            </div>
        </div>



    
    </>)

}
export default Cards