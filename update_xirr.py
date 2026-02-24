from engine import rebuild_holdings
import database
database.initialize_database()
rebuild_holdings()
print("Holdings rebuilt.")
