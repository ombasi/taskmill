import random

from models.product import Product


class ProductService:

    # =====================================
    # Random Product
    # =====================================

    @staticmethod
    def random_product(user):

        membership = user.membership

        products = Product.query.filter(

            Product.active == True,

            Product.price <= membership.maximum_product,

            Product.stock > 0

        ).all()

        if not products:
            return None

        return random.choice(products)

    # =====================================
    # Random Combo Product
    # =====================================

    @staticmethod
    def random_combo(user):

        membership = user.membership

        products = Product.query.filter(

            Product.active == True,

            Product.price > membership.maximum_product,

            Product.stock > 0

        ).all()

        if not products:
            return None

        return random.choice(products)

    # =====================================
    # Reduce Stock
    # =====================================

    @staticmethod
    def reduce_stock(product):

        if product.stock > 0:

            product.stock -= 1

    # =====================================
    # Increase Stock
    # =====================================

    @staticmethod
    def increase_stock(product):

        product.stock += 1

    # =====================================
    # Available Products
    # =====================================

    @staticmethod
    def available_products(user):

        membership = user.membership

        return Product.query.filter(

            Product.active == True,

            Product.price <= membership.maximum_product,

            Product.stock > 0

        ).all()

    # =====================================
    # Combo Products
    # =====================================

    @staticmethod
    def combo_products(user):

        membership = user.membership

        return Product.query.filter(

            Product.active == True,

            Product.price > membership.maximum_product,

            Product.stock > 0

        ).all()
    @staticmethod
def random_product(user):

    membership = user.membership

    return Product.query.filter(

        Product.membership_id == membership.id,

        Product.active == True

    ).order_by(

        func.random()

    ).first()